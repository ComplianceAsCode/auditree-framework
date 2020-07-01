# -*- mode:python; coding:utf-8 -*-
# Copyright (c) 2020 IBM Corp. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Compliance report build automation module."""

import copy
import datetime
import json
import logging
import os
import traceback

from compliance.config import get_config
from compliance.evidence import get_evidence_by_path

import jinja2

log = logging.getLogger('compliance.report')


class ReportBuilder(object):
    """This class builds all the required reports for the tests."""

    def __init__(self, locker, results, controls):
        """
        Construct and initialize the file descriptor notifier object.

        :param locker: the locker to be used.
        :param results: the dictionary of the test results.
        :param controls: the control descriptor that manages accreditations.
        """
        self.locker = locker
        self.results = results
        self.controls = controls

    def build(self):
        """Build the reports and store them in the locker."""
        test_by_class = self._get_test_by_class()
        with self.locker:
            self._generate_reports(test_by_class)
            self._generate_raw_results()

    def render_evidence_with_template(self, evidence, test_obj):
        """
        Render content based on a template.

        If template system was selected, this method renders the content
        using the template for the given evidence.

        :param evidence: the evidence object to be rendered using its template.
        :param test_obj: test object which has all the tests for check.
        """
        if evidence.content is not None:
            return
        tmpl_path = self.get_template_for(test_obj, evidence)
        path, filename = os.path.split(tmpl_path)
        now = datetime.datetime.utcnow()
        context = {
            'test': test_obj,
            'results': self.results,
            'all_successes': test_obj.successes_for_check(self.results),
            'all_failures': test_obj.failures_for_check(self.results),
            'all_warnings': test_obj.warnings_for_check(self.results),
            'evidence': evidence,
            'builder': self,
            'now': now
        }
        content = jinja2.Environment(
            loader=jinja2.FileSystemLoader(path),
            autoescape=True,
        ).get_template(filename).render(context)
        evidence.set_content(content)

    def get_template_for(self, test_obj, evidence):
        """
        Provide the file path of the template associated to the given evidence.

        :param test_report_obj: the test object that needs to create report.
        :param evidence: the ReportEvidence object expected.
        """
        tmpl_dir = get_config().get_template_dir(test_obj)
        if tmpl_dir is None:
            raise RuntimeError(
                f'Unable to find template directory for test {test_obj.id()}'
            )
        tmpl_path = os.path.join(tmpl_dir, evidence.path + '.tmpl')
        if not os.path.exists(tmpl_path):
            return os.path.join(tmpl_dir, 'default.md.tmpl')
        return tmpl_path

    def _generate_raw_results(self):
        """Create a check results JSON file stored in the evidence locker."""
        self.locker.add_content_to_locker(
            json.dumps(
                self._munge_chk_results(self.locker.get_reports_metadata()),
                indent=2,
                sort_keys=True,
                separators=(',', ': '),
                skipkeys=True,
                default=str
            ),
            filename='check_results.json'
        )

    def _munge_chk_results(self, rpt_metadata):
        """
        Combine the check execution results with associated reports metadata.

        This method combines check results with details about associated
        reports and evidences used, found in the report metadata.  It
        returns a dictionary keyed by check class dot path.
        """
        chk_results = {}
        for rpt, meta in rpt_metadata.items():
            check_methods = {}
            if not meta.get('checks'):
                continue
            for check in meta['checks']:
                check_class, check_method = check.rsplit('.', 1)
                check_methods[check_method] = {}
                if self.results.get(check):
                    test = self.results[check]['test'].test
                    check_methods[check_method] = {
                        'status': self.results[check]['status'],
                        'timestamp': self.results[check]['timestamp'],
                        'warnings': test.warnings,
                        'failures': test.failures,
                        'successes': test.successes,
                        'warnings_count': test.warnings_count(),
                        'failures_count': test.failures_count(),
                        'successes_count': test.successes_count()
                    }
            if not chk_results.get(check_class):
                chk_results[check_class] = {
                    'checks': check_methods,
                    'reports': {
                        rpt: meta['description']
                    },
                    'evidence': meta['evidence'],
                    'accreditations': list(
                        self.controls.get_accreditations(check_class)
                    )
                }
            else:
                chk_results[check_class]['reports'][rpt] = meta['description']
        return chk_results

    def _get_test_by_class(self):
        """
        Collect one test object per ComplianceTest class.

        This is required to group tests into a single report. Note that
        we only need _one_ test object of a certain ComplianceTest and
        it its attributes get updated with each test object found for
        that class. This will be useful for templates, where a test
        object is passed and it will holds all possible attributes.
        """
        retval = {}
        for _, info in self.results.items():
            test_obj = info['test'].test
            if not hasattr(test_obj, 'get_reports'):
                continue

            test_class = test_obj.__class__
            if test_class in retval:
                retval[test_class].__dict__.update(test_obj.__dict__)
            else:
                retval[test_class] = copy.copy(test_obj)
        return retval

    def _generate_reports(self, test_by_class):
        """
        Generate the reports per-test-class basis.

        If ``test.get_reports()`` replies with a list of evidence paths,
        then the template system is used. If not, a list of evidences
        is expected.

        :param test_by_class: a dictionary of {class: test_obj}.
        """
        for test_class, test_obj in test_by_class.items():
            # get a list of all test objects related to this test class
            test_infos = [
                info for info in self.results.values()
                if info['test'].test.__class__ == test_class
            ]

            try:
                reports = test_obj.get_reports()
            except (AttributeError, ValueError) as e:
                log.warning(
                    f'\n  Failed to generate report for {test_obj.id()}'
                    f'\n  Error: {e}'
                )
                for info in test_infos:
                    info['status'] = 'error'
                continue

            for r in reports:
                try:
                    self.__render_report(r, test_obj, test_infos)
                except Exception as e:
                    log.warning(
                        f'\n  Failed to generate report for {test_obj.id()}'
                        f'\n  Error: {e.__class__.__name__} '
                        f'- {traceback.format_exc(-5)}'
                    )
                    for info in test_infos:
                        info['status'] = 'error'

    def _get_checks(self, test_obj):
        """
        Get the check paths for all checks in the test object.

        :param test_obj: test object which has all the tests for check.
        """
        checks = []
        for test_id, info in self.results.items():
            if info['test'].test == test_obj:
                checks = [
                    c for c in self.results.keys()
                    if c.startswith(test_id.rsplit('.', 1)[0])
                ]
                break
        return checks

    def __render_report(self, report, test_obj, test_infos):
        evidence = report
        if isinstance(report, str):
            path = report
            if not report.startswith('reports/'):
                path = 'reports/' + report
            evidence = get_evidence_by_path(path)

        self.render_evidence_with_template(evidence, test_obj)

        self.locker.add_evidence(
            evidence,
            self._get_checks(test_obj),
            test_obj.evidences_for_check(self.results)
        )
        for test_obj_orig in [i['test'].test for i in test_infos]:
            test_obj_orig.reports.append(evidence)
