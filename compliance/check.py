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
"""Compliance check automation module."""

import unittest
from datetime import datetime as dt

from compliance.config import get_config
from compliance.utils.exceptions import EvidenceNotFoundError

import inflection


class ComplianceCheck(unittest.TestCase):
    """Compliance check automation TestCase class."""

    def __init__(self, *args, **kwargs):
        """Construct and initialize the check test object."""
        super(ComplianceCheck, self).__init__(*args, **kwargs)
        if hasattr(ComplianceCheck, "config"):
            self.config = ComplianceCheck.config
        else:
            self.config = get_config()

    @property
    def title(self):
        """Check title, normally used in check reports."""
        raise NotImplementedError(
            f"Property title not implemented on {self.__class__.__name__}"
        )

    @property
    def reports(self):
        """List of the check reports."""
        if "_reports" not in self.__dict__.keys():
            self._reports = []
        return self._reports

    @property
    def runbook_url(self):
        """
        Runbook URL associated with the check.

        If runbook links are enabled in the configuration, the value returned
        is based on the runbook base URL and the check's class name.  It is
        assumed that the runbook exists and is in HTML format.
        """
        runbook_enabled = self.config.get("runbooks.enabled")
        runbook_baseurl = self.config.get("runbooks.base_url")
        if runbook_baseurl and runbook_enabled:
            runbook_name = inflection.underscore(self.__class__.__name__)
            return f"{runbook_baseurl}/{runbook_name}.html"

    @property
    def fixed_failure_count(self):
        """Count of failures fixed by the fix routine."""
        if "_fixed_failure_count" not in self.__dict__.keys():
            self._fixed_failure_count = 0
        return self._fixed_failure_count

    @fixed_failure_count.setter
    def fixed_failure_count(self, value):
        self._fixed_failure_count = value

    @property
    def warnings(self):
        """Warnings as a property for each check."""
        if not hasattr(self, "_warnings"):
            self._warnings = {}
        return self._warnings

    @property
    def failures(self):
        """Failures as a property for each check."""
        if not hasattr(self, "_failures"):
            self._failures = {}
        return self._failures

    @property
    def successes(self):
        """Successes as a property for each check."""
        if not hasattr(self, "_successes"):
            self._successes = {}
        return self._successes

    @property
    def evidence_metadata(self):
        """Metadata of all evidence used by each check as a property."""
        if not hasattr(self, "_evidence_metadata"):
            self._evidence_metadata = {}
        return self._evidence_metadata

    def id(self):  # noqa: A003
        """Reset the test id if it has been transplanted and return it."""
        return_id = super(ComplianceCheck, self).id()
        origin = getattr(self, "__origin_module__", None)
        if origin and not return_id.startswith(origin):
            original = ".".join([self.__origin_module__, self.__class__.__name__])
            transplanted = ".".join(
                [
                    self.__class__.__module__,
                    getattr(self.__class__, "__qualname__", self.__class__.__name__),
                ]
            )
            return return_id.replace(transplanted, original)
        return return_id

    def total_issues_count(self, results):
        """
        Total number of issues as property for the check.

        :param results: contains all the test results.
        """
        return self.failures_for_check_count(results) + self.warnings_for_check_count(
            results
        )

    def add_warnings(self, section_key, section_value):
        """
        Add warnings for each check.

        :param: section_key: key for the warnings.
        :param: section_value: all the warnings for that key.
        """
        self.warnings.setdefault(section_key, [])
        if isinstance(section_value, (list, set)):
            self.warnings[section_key].extend(section_value)
        else:
            self.warnings[section_key].append(section_value)

    def warnings_for_check(self, results):
        """
        Provide warnings associated with all tests in the check.

        :param results: contains all the test results.
        """
        w = {}
        for t in self._get_all_test_objs(results):
            for k, v in t.warnings.items():
                w.setdefault(k, []).extend(v)
        return w

    def warnings_for_check_count(self, results):
        """
        Count failures for all tests in the check.

        :param results: contains all the test results.
        """
        return sum(t.warnings_count() for t in self._get_all_test_objs(results))

    def warnings_count(self):
        """Count warnings for a specific test."""
        return sum(len(v) for _, v in self.warnings.items())

    def add_failures(self, section_key, section_value):
        """
        Add failures for each check.

        :param: section_key: key for the failures.
        :param: section_value: all the failures for that key.
        """
        self.failures.setdefault(section_key, [])
        if isinstance(section_value, (list, set)):
            self.failures[section_key].extend(section_value)
        else:
            self.failures[section_key].append(section_value)

    def failures_for_check(self, results):
        """
        Provide failures associated with all tests in the check.

        :param results: contains all the test results.
        """
        f = {}
        for t in self._get_all_test_objs(results):
            for k, v in t.failures.items():
                f.setdefault(k, []).extend(v)
        return f

    def failures_for_check_count(self, results):
        """
        Count failures for all tests in check.

        :param results: contains all the test results.
        """
        return sum(t.failures_count() for t in self._get_all_test_objs(results))

    def failures_count(self):
        """Count failures for a specific test."""
        return sum(len(v) for _, v in self.failures.items())

    def add_successes(self, section_key, section_value):
        """
        Add successes for each check.

        :param: section_key: key for the successes.
        :param: section_value: all the successes for that key.
        """
        self.successes.setdefault(section_key, [])
        if isinstance(section_value, (list, set)):
            self.successes[section_key].extend(section_value)
        else:
            self.successes[section_key].append(section_value)

    def successes_for_check(self, results):
        """
        Provide successes associated with all tests in the check.

        :param results: contains all the test results.
        """
        s = {}
        for t in self._get_all_test_objs(results):
            for k, v in t.successes.items():
                s.setdefault(k, []).extend(v)
        return s

    def successes_for_check_count(self, results):
        """
        Count successes for all tests in check.

        :param results: contains all the test results.
        """
        return sum(t.successes_count() for t in self._get_all_test_objs(results))

    def successes_count(self):
        """Count successes for a specific test."""
        return sum(len(v) for _, v in self.successes.items())

    def run(self, result=None):
        """
        Override the unittest.TestCase.run method.

        Decorates ``test_`` methods by adding common functionality
        (e.g. failures count check).
        """

        def wrapper(method):
            def check_failures():
                method()
                self.assertEquals(self.failures_count(), 0)

            return check_failures

        test_method = getattr(self, self._testMethodName)
        setattr(self, self._testMethodName, wrapper(test_method))
        super(ComplianceCheck, self).run(result)

    def add_issue_if_diff(self, actual, expected, msg, as_warning=False):
        """
        Add failures/warnings if differences exist between actual and expected.

        :param actual: the "actual" set items.
        :param expected: the "expected" set items.
        :param msg: the section key used if differences are found.
        :param as_warning: warn if True, fail if False.
        """
        diff = set(actual) - set(expected)
        if not diff:
            return
        if as_warning:
            self.add_warnings(msg, sorted(diff))
        else:
            self.add_failures(msg, sorted(diff))

    def get_historical_evidence(self, evidence_path, evidence_dt):
        """
        Retrieve historical evidence from the locker and track as metadata.

        :param evidence_path: the evidence path.
        :param evidence_dt: the evidence date.
        """
        evidence = self.locker.get_evidence(evidence_path, True, evidence_dt)
        self.add_evidence_metadata(
            evidence_path, evidence_dt=evidence_dt, evidence_locker=evidence.locker
        )
        return evidence

    def add_evidence_metadata(
        self, evidence_path, evidence_dt=None, evidence_locker=None
    ):
        """
        Add evidence metadata to the evidence_metadata property of each check.

        :param evidence_path: the evidence path.
        :param evidence_dt: the evidence date.
        :param evidence_locker: the locker the evidence was retrieved from.
          Use when historical evidence is found in a secondary locker.
        """
        locker = evidence_locker or self.locker
        metadata = locker.get_evidence_metadata(evidence_path, evidence_dt)
        if not metadata:
            ev_dt_str = (evidence_dt or dt.utcnow()).strftime("%Y-%m-%d")
            raise EvidenceNotFoundError(
                f"Evidence {evidence_path} is not found in the locker "
                f"for {ev_dt_str}. It may not be a valid evidence path."
            )
        metadata.update({"path": evidence_path, "locker_url": locker.repo_url})
        if metadata.get("partitions"):
            path, file_name = evidence_path.rsplit("/", 1)
            partitions = {}
            for part_hash, part_key in metadata["partitions"].items():
                partitions[part_hash] = {
                    "key": part_key,
                    "commit_sha": locker.get_latest_commit(
                        f"{path}/{part_hash}_{file_name}", evidence_dt
                    ).hexsha,
                }
            metadata["partitions"] = partitions
        else:
            metadata["commit_sha"] = locker.get_latest_commit(
                evidence_path, evidence_dt
            ).hexsha
        metadata.pop("tombstones", None)
        evidence_meta_key = (evidence_path, metadata["last_update"])
        self.evidence_metadata[evidence_meta_key] = metadata

    def evidences_for_check(self, results):
        """
        Provide evidences used by all tests in the check.

        :param results: contains all the test results.
        """
        evidences = {}
        for test_obj in self._get_all_test_objs(results):
            evidences.update(test_obj.evidence_metadata)
        return list(evidences.values())

    def _get_all_test_objs(self, results):
        """
        Provide all completed tests from the test results.

        All completed tests that are associated with this
        check class are returned.
        """
        return [
            info["test"].test
            for info in results.values()
            if info["test"].test.__class__ == self.__class__
        ]
