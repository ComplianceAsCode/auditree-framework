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
"""Compliance automation check tests module."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, call, create_autospec

from compliance.check import ComplianceCheck
from compliance.config import ComplianceConfig
from compliance.locker import Locker

from git import Commit


class ComplianceCheckTest(unittest.TestCase):
    """ComplianceCheck test class."""

    def setUp(self):
        """Initialize each test."""
        # Since unittest.TestCase needs a method for running the test
        # (runTest, by default) and ComplianceCheck is a child of
        # unittest.TestCase, we must pass a method in the
        # constructor (otherwise, we will get a ValueError). Since we
        # don't need this method, passing ``__doc__`` is enough for
        # building a ComplianceCheck object successfully.
        self.check = ComplianceCheck("__doc__")

        # Ensures that the check object has a (mocked) locker attribute/object
        # on it as expected.
        self.check.locker = create_autospec(Locker)
        self.check.locker.repo_url = "https://my.locker.url"

    def test_title(self):
        """Check title raises an exception in the base class."""
        with self.assertRaises(NotImplementedError) as cm:
            self.check.title
        self.assertEqual(
            str(cm.exception), "Property title not implemented on ComplianceCheck"
        )

    def test_config(self):
        """Check that the config property returns a ComplianceConfig object."""
        self.assertIsInstance(self.check.config, ComplianceConfig)

    def test_reports(self):
        """Check reports property."""
        self.assertEqual(self.check.reports, [])
        self.check.reports.append("dummy")
        self.assertEqual(self.check.reports, ["dummy"])

    def test_disabled_runbook_url(self):
        """Check runbook URL is none - disabled."""
        self.check.config._config.update(
            {"runbooks": {"enabled": False, "base_url": "http://configuredrunbooks"}}
        )
        self.assertEqual(self.check.runbook_url, None)

    def test_unconfigured_runbook_url(self):
        """Check runbook URL is none - not configured."""
        self.check.config._config.update(
            {"runbooks": {"enabled": True, "base_url": ""}}
        )
        self.assertEqual(self.check.runbook_url, None)

    def test_configured_runbook_url(self):
        """Check runbook URL is set."""
        self.check.config._config.update(
            {"runbooks": {"enabled": True, "base_url": "http://configuredrunbooks"}}
        )
        self.assertEqual(
            self.check.runbook_url, "http://configuredrunbooks/compliance_check.html"
        )

    def test_evidence_metadata(self):
        """Check evidence_metadata property."""
        self.assertEqual(self.check.evidence_metadata, {})

    def test_fixed_failure_count(self):
        """Check fixed_failure_count property."""
        self.assertEqual(self.check.fixed_failure_count, 0)
        self.check.fixed_failure_count = 100
        self.assertEqual(self.check.fixed_failure_count, 100)

    def test_failures(self):
        """Test failures property, and the length of dict and of type."""
        self.assertEqual(self.check.failures, {})
        self.check.add_failures("fail_type", "fail_for")
        self.check.add_failures("fail_type_2", "fail_for_2")
        expected_failure = {"fail_type": ["fail_for"], "fail_type_2": ["fail_for_2"]}
        self.assertEqual(expected_failure, self.check.failures)
        self.assertEqual(self.check.failures_count(), 2)

    def test_warnings(self):
        """Test warning property and if key does not exist, throws KeyError."""
        self.check._failures = {}
        self.assertEqual(self.check.warnings, {})
        self.check.add_warnings("warn_type", "warn_for")
        expected_warning = {"warn_type": ["warn_for"]}
        self.assertEqual(expected_warning, self.check.warnings)

    def test_add_issue_if_diff_failure(self):
        """Test add_issue_if_diff adds a failure as expected."""
        # Throw a fail and make sure it did not warn
        self.check.add_issue_if_diff({1, 2, 3, 5}, {1, 2, 3, 4}, "Extra users found")
        self.assertEqual(self.check.failures_count(), 1)
        self.assertEqual(self.check.warnings_count(), 0)
        self.assertEqual(self.check._failures, {"Extra users found": [5]})

    def test_add_issue_if_diff_warning(self):
        """Test add_issue_if_diff adds a warning as expected."""
        # Throw a fail and make sure it did not warn
        self.check.add_issue_if_diff(
            {1, 2, 3, 4}, {1, 2, 3, 5}, "Users not found", True
        )
        self.assertEqual(self.check.failures_count(), 0)
        self.assertEqual(self.check.warnings_count(), 1)
        self.assertEqual(self.check._warnings, {"Users not found": [4]})

    def test_add_issue_if_diff_no_diff(self):
        """Test add_issue_if_diff does not add a fail/warning when no diff."""
        # Ensure no issues are raised when there is no diff
        self.check.add_issue_if_diff([], [], "FAILED")
        self.assertEqual(self.check.failures_count(), 0)
        self.assertEqual(self.check.warnings_count(), 0)

    def test_add_evidence_metadata(self):
        """Test evidence_metadata is populated correctly."""
        commit_mock = create_autospec(Commit)
        commit_mock.hexsha = "mycommitsha"
        self.check.locker.get_latest_commit = MagicMock()
        self.check.locker.get_latest_commit.return_value = commit_mock
        self.check.locker.get_evidence_metadata = MagicMock()
        self.check.locker.get_evidence_metadata.return_value = {
            "foo": "bar",
            "last_update": "2019-11-15",
        }
        ev_date = datetime(2019, 11, 15)

        self.check.add_evidence_metadata("raw/foo/foo.json", ev_date)

        self.check.locker.get_latest_commit.assert_called_once_with(
            "raw/foo/foo.json", ev_date
        )
        self.check.locker.get_evidence_metadata.assert_called_once_with(
            "raw/foo/foo.json", ev_date
        )
        self.assertEqual(
            self.check.evidence_metadata,
            {
                ("raw/foo/foo.json", "2019-11-15"): {
                    "path": "raw/foo/foo.json",
                    "commit_sha": "mycommitsha",
                    "foo": "bar",
                    "last_update": "2019-11-15",
                    "locker_url": "https://my.locker.url",
                }
            },
        )

    def test_add_partitioned_evidence_metadata(self):
        """Test evidence_metadata is populated correctly for partitions."""
        commit_mock = create_autospec(Commit)
        commit_mock.hexsha = "mycommitsha"
        self.check.locker.get_latest_commit = MagicMock()
        self.check.locker.get_latest_commit.return_value = commit_mock
        self.check.locker.get_evidence_metadata = MagicMock()
        self.check.locker.get_evidence_metadata.return_value = {
            "foo": "bar",
            "last_update": "2019-11-15",
            "partitions": {"123": ["foo"], "456": ["bar"]},
            "tombstones": "zombie",
        }
        ev_date = datetime(2019, 11, 15)

        self.check.add_evidence_metadata("raw/foo/foo.json", ev_date)

        self.assertEqual(self.check.locker.get_latest_commit.call_count, 2)
        self.check.locker.get_latest_commit.assert_has_calls(
            [
                call("raw/foo/123_foo.json", ev_date),
                call("raw/foo/456_foo.json", ev_date),
            ],
            any_order=True,
        )
        self.check.locker.get_evidence_metadata.assert_called_once_with(
            "raw/foo/foo.json", ev_date
        )
        self.assertEqual(
            self.check.evidence_metadata,
            {
                ("raw/foo/foo.json", "2019-11-15"): {
                    "path": "raw/foo/foo.json",
                    "partitions": {
                        "123": {"key": ["foo"], "commit_sha": "mycommitsha"},
                        "456": {"key": ["bar"], "commit_sha": "mycommitsha"},
                    },
                    "foo": "bar",
                    "last_update": "2019-11-15",
                    "locker_url": "https://my.locker.url",
                }
            },
        )
