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
"""Compliance automation fixer tests module."""

import time
import unittest
from io import StringIO
from unittest.mock import patch

from compliance.check import ComplianceCheck
from compliance.fix import Fixer
from compliance.runners import ComplianceTestWrapper

from .. import build_compliance_check_obj


class ComplianceFixerTest(unittest.TestCase):
    """Compliance Fixer test class."""

    @patch("compliance.fix.get_config")
    def setUp(self, config_mock):
        """Initialize each test."""
        compliance_check1 = build_compliance_check_obj(
            "Dummy1Check", "dummy1", "Report for dummy1", ["test_dummy1_test1"], True
        )
        compliance_check2 = build_compliance_check_obj(
            "Dummy2Check", "dummy2", "Report for dummy2", ["test_dummy2_test1"], True
        )
        compliance_check3 = build_compliance_check_obj(
            "Dummy3Check",
            "dummy3",
            "Report for dummy3",
            ["test_dummy3_test1", "test_dummy3_test2"],
            True,
        )
        compliance_check4 = build_compliance_check_obj(
            "Dummy4Check", "dummy4", "Report for dummy4", ["test_dummy4_test1"], False
        )
        compliance_check5 = build_compliance_check_obj(
            "Dummy5Check", "dummy5", "Report for dummy5", [], False
        )

        test1_obj = ComplianceTestWrapper(compliance_check1)
        test2_obj = ComplianceTestWrapper(compliance_check2)
        test3_obj = ComplianceTestWrapper(compliance_check3)
        test4_obj = ComplianceTestWrapper(compliance_check4)
        test5_obj = ComplianceTestWrapper(compliance_check5)

        results_empty = {}
        results_full = {
            "compliance.dummy_accred.test_dummy1_test1": {
                "status": "pass",
                "timestamp": time.time(),
                "test": test1_obj,
            },
            "compliance.dummy_accred.test_dummy2_test1": {
                "status": "error",
                "timestamp": time.time(),
                "test": test2_obj,
            },
            "compliance.dummy_accred.test_dummy3_test1": {
                "status": "fail",
                "timestamp": time.time(),
                "test": test3_obj,
            },
            "compliance.dummy_accred.test_dummy3_test2": {
                "status": "fail",
                "timestamp": time.time(),
                "test": test3_obj,
            },
            "compliance.dummy_accred.test_dummy4_test1": {
                "status": "fail",
                "timestamp": time.time(),
                "test": test4_obj,
            },
            # this test doesn't actually exist (check when
            # no tests defined in a class)
            "compliance.dummy_accred.test_dummy5_test0": {
                "status": "fail",
                "timestamp": time.time(),
                "test": test5_obj,
            },
        }

        self.empty_results_out = StringIO()
        self.empty_results_fixer = Fixer(
            results_empty, dry_run=False, out=self.empty_results_out
        )

        self.real_out = StringIO()
        self.real_fixer = Fixer(results_full, dry_run=False, out=self.real_out)

        self.dry_run_out = StringIO()
        self.dry_run_fixer = Fixer(results_full, dry_run=True, out=self.dry_run_out)

    def test_empty_results_fix(self):
        """Check that the fixer does nothing if there are no results."""
        self.empty_results_fixer.fix()

        self.assertEqual(self.empty_results_out.getvalue(), "")

    def test_real_fix(self):
        """Check that the fixer works when not in dry-run mode."""
        self.real_fixer.fix()

        self.assertEqual(self.real_out.getvalue(), "")
        self.assertEqual(
            sorted(self.dry_run_fixer._results.keys()),
            [
                "compliance.dummy_accred.test_dummy1_test1",
                "compliance.dummy_accred.test_dummy2_test1",
                "compliance.dummy_accred.test_dummy3_test1",
                "compliance.dummy_accred.test_dummy3_test2",
                "compliance.dummy_accred.test_dummy4_test1",
                "compliance.dummy_accred.test_dummy5_test0",
            ],
        )

        for k in sorted(self.real_fixer._results.keys()):
            method_name = k.split(".")[-1]
            result = self.real_fixer._results[k]
            status = result["status"]
            test = result["test"].test

            self.assertTrue(issubclass(test.__class__, ComplianceCheck))
            if status == "fail":
                # dummy5 doesn't actually have any tests defined
                if test.title == "dummy5":
                    test.fix_one.assert_not_called()
                else:
                    test.fix_one.assert_any_call(
                        creds=self.real_fixer._creds, param=method_name
                    )

                # dummy4's fix function has been set to return False
                if test.title == "dummy4":
                    self.assertEqual(test.fixed_failure_count, 0)
                else:
                    self.assertEqual(test.fixed_failure_count, len(test.tests))
            else:
                test.fix_one.assert_not_called
                self.assertEqual(test.fixed_failure_count, 0)

    def test_dry_run_fix(self):
        """Check that the fixer works in dry-run mode."""
        self.dry_run_fixer.fix()

        # only check things not already checked in the real fixer test above

        out_msgs = sorted(self.dry_run_out.getvalue().strip("\n").split("\n"))
        self.assertEqual(
            out_msgs,
            [
                "DRY-RUN: Fixing test_dummy3_test1",
                "DRY-RUN: Fixing test_dummy3_test2",
                "DRY-RUN: Fixing test_dummy4_test1",
            ],
        )

        for k in sorted(self.dry_run_fixer._results.keys()):
            result = self.dry_run_fixer._results[k]
            status = result["status"]
            test = result["test"].test

            if status == "fail":
                test.fix_one.assert_not_called
                self.assertEqual(test.fixed_failure_count, 0)
