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
import logging
import re
import traceback
from pathlib import Path, PurePath

from compliance.config import get_config
from compliance.evidence import get_evidence_by_path
from compliance.locker import READMES
from compliance.utils.data_parse import format_json

import jinja2

log = logging.getLogger("compliance.report")


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
            rpt_metadata = self.locker.get_reports_metadata()
            self.generate_toc(rpt_metadata)
            self.generate_check_results(rpt_metadata)

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
        tmpl_path = PurePath(self.get_template_for(test_obj, evidence))
        now = datetime.datetime.utcnow()
        context = {
            "test": test_obj,
            "results": self.results,
            "all_successes": test_obj.successes_for_check(self.results),
            "all_failures": test_obj.failures_for_check(self.results),
            "all_warnings": test_obj.warnings_for_check(self.results),
            "evidence": evidence,
            "builder": self,
            "now": now,
        }
        loader = jinja2.FileSystemLoader(str(tmpl_path.parent))
        env = jinja2.Environment(loader=loader, autoescape=True)
        evidence.set_content(env.get_template(tmpl_path.name).render(context))

    def get_template_for(self, test_obj, evidence):
        """
        Provide the file path of the template associated to the given evidence.

        :param test_report_obj: the test object that needs to create report.
        :param evidence: the ReportEvidence object expected.
        """
        tmpl_dir = get_config().get_template_dir(test_obj)
        if tmpl_dir is None:
            raise RuntimeError(
                f"Unable to find template directory for test {test_obj.id()}"
            )
        tmpl_path = Path(tmpl_dir, f"{evidence.path}.tmpl")
        if not tmpl_path.is_file():
            tmpl_path = PurePath(tmpl_dir, "default.md.tmpl")
        return str(tmpl_path)

    def generate_toc(self, rpt_metadata):
        """
        Generate a check reports table of contents.

        This method generates a TOC based on all report evidence metadata and
        appends that TOC to the bottom of an evidence locker's README.md file.

        :param rpt_metadata: Metadata from all report evidence index.json files
        """
        path = Path(self.locker.local_path)
        files = sorted(
            str(f) for f in path.iterdir() if f.is_file() and f.name in READMES
        )
        readme = files[0] if files else "README.md"
        content_as_str = re.sub(
            "\n{2,}", "\n\n", self.locker.get_content_from_locker(filename=readme) or ""
        )
        rpts = []
        for rpt, meta in rpt_metadata.items():
            if meta.get("pruned_by"):
                continue
            rpt_descr = meta["description"] or PurePath(rpt).name
            rpt_url = self.locker.get_remote_location(rpt, False)
            check = meta.get("checks", ["N/A"])[0].rsplit(".", 1).pop(0)
            evidences = []
            for ev in meta.get("evidence", []):
                ev_path = PurePath(ev["path"])
                ev_descr = ev["description"] or ev_path.name
                ev_locker_url = ev.get("locker_url", self.locker.repo_url)
                if not ev.get("partitions"):
                    ev_url = self.locker.get_remote_location(
                        ev["path"], False, ev["commit_sha"], ev_locker_url
                    )
                    evidences.append(
                        {"descr": ev_descr, "url": ev_url, "from": ev["last_update"]}
                    )
                else:
                    for hash_key, part in ev["partitions"].items():
                        ev_part_descr = f"{ev_descr} - {hash_key} partition"
                        ev_name = f"{hash_key}_{ev_path.name}"
                        ev_url = self.locker.get_remote_location(
                            str(ev_path.with_name(ev_name)),
                            False,
                            part["commit_sha"],
                            ev_locker_url,
                        )
                        evidences.append(
                            {
                                "descr": ev_part_descr,
                                "url": ev_url,
                                "from": ev["last_update"],
                            }
                        )
            accreditations = sorted(self.controls.get_accreditations(check))
            rpts.append(
                {
                    "descr": rpt_descr,
                    "url": rpt_url,
                    "check": check,
                    "accreditations": ", ".join(accreditations) or "N/A",
                    "from": meta["last_update"],
                    "evidences": sorted(evidences, key=lambda ev: ev["descr"]),
                }
            )
        context = {
            "original": content_as_str.split("\n") if content_as_str else [],
            "reports": sorted(rpts, key=lambda r: r["descr"]),
        }
        loader = jinja2.FileSystemLoader(get_config().get_template_dir(self))
        env = jinja2.Environment(loader=loader, autoescape=True)
        content = env.get_template("readme_toc.md.tmpl").render(context)
        self.locker.add_content_to_locker(content, filename=readme)

    def generate_check_results(self, rpt_metadata):
        """
        Combine the check execution results with associated reports metadata.

        This method combines check results with details about associated
        reports and evidences used, found in the report metadata.  It
        returns a dictionary keyed by check class dot path.

        :param rpt_metadata: Metadata from all report evidence index.json files
        """
        chk_results = {}
        for rpt, meta in rpt_metadata.items():
            check_methods = {}
            if not meta.get("checks"):
                continue
            for check in meta["checks"]:
                check_class, check_method = check.rsplit(".", 1)
                check_methods[check_method] = {}
                if self.results.get(check):
                    test = self.results[check]["test"].test
                    check_methods[check_method] = {
                        "status": self.results[check]["status"],
                        "timestamp": self.results[check]["timestamp"],
                        "warnings": test.warnings,
                        "failures": test.failures,
                        "successes": test.successes,
                        "warnings_count": test.warnings_count(),
                        "failures_count": test.failures_count(),
                        "successes_count": test.successes_count(),
                    }
            if not chk_results.get(check_class):
                chk_results[check_class] = {
                    "checks": check_methods,
                    "reports": {rpt: meta["description"]},
                    "evidence": meta["evidence"],
                    "accreditations": list(
                        self.controls.get_accreditations(check_class)
                    ),
                }
            else:
                chk_results[check_class]["reports"][rpt] = meta["description"]
        self.locker.add_content_to_locker(
            format_json(chk_results, skipkeys=True, default=str),
            filename="check_results.json",
        )

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
            test_obj = info["test"].test
            if not hasattr(test_obj, "get_reports"):
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
                info
                for info in self.results.values()
                if info["test"].test.__class__ == test_class
            ]
            try:
                reports = test_obj.get_reports()
            except (AttributeError, ValueError) as e:
                log.warning(
                    f"\n  Failed to generate report for {test_obj.id()}"
                    f"\n  Error: {e}"
                )
                for info in test_infos:
                    info["status"] = "error"
                continue
            for r in reports:
                try:
                    self.__render_report(r, test_obj, test_infos)
                except Exception as e:
                    log.warning(
                        f"\n  Failed to generate report for {test_obj.id()}"
                        f"\n  Error: {e.__class__.__name__} "
                        f"- {traceback.format_exc(-5)}"
                    )
                    for info in test_infos:
                        info["status"] = "error"

    def _get_checks(self, test_obj):
        """
        Get the check paths for all checks in the test object.

        :param test_obj: test object which has all the tests for check.
        """
        checks = []
        for test_id, info in self.results.items():
            if info["test"].test == test_obj:
                checks = [
                    c
                    for c in self.results.keys()
                    if c.startswith(test_id.rsplit(".", 1)[0])
                ]
                break
        return checks

    def __render_report(self, report, test_obj, test_infos):
        evidence = report
        if isinstance(report, str):
            path = report
            if not report.startswith("reports/"):
                path = "reports/" + report
            evidence = get_evidence_by_path(path)
        self.render_evidence_with_template(evidence, test_obj)
        self.locker.add_evidence(
            evidence,
            self._get_checks(test_obj),
            test_obj.evidences_for_check(self.results),
        )
        for test_obj_orig in [i["test"].test for i in test_infos]:
            test_obj_orig.reports.append(evidence)
