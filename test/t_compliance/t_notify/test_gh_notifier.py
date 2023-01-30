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
"""Compliance automation GH notifier tests module."""

import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import GHIssuesNotifier

from .. import build_compliance_check_obj


class GHNotifierTest(unittest.TestCase):
    """GHIssuesNotifier test class."""

    def setUp(self):
        """Initialize each test."""
        self.results = {}
        for status in ["pass", "fail", "error", "warn"]:
            name, result = self._generate_result(status)
            self.results[name] = result
        self.si_patcher = patch("compliance.notify.Github.search_issues")
        self.search_issues_mock = self.si_patcher.start()
        self.ai_patcher = patch("compliance.notify.Github.add_issue")
        self.add_issue_mock = self.ai_patcher.start()
        self.pi_patcher = patch("compliance.notify.Github.patch_issue")
        self.patch_issue_mock = self.pi_patcher.start()
        self.aic_patcher = patch("compliance.notify.Github.add_issue_comment")
        self.add_issue_comment_mock = self.aic_patcher.start()
        self.gap_patcher = patch("compliance.notify.Github.get_all_projects")
        self.get_all_projects_mock = self.gap_patcher.start()
        self.gc_patcher = patch("compliance.notify.Github.get_columns")
        self.get_columns_mock = self.gc_patcher.start()
        self.gac_patcher = patch("compliance.notify.Github.get_all_cards")
        self.get_all_cards_mock = self.gac_patcher.start()
        self.ac_patcher = patch("compliance.notify.Github.add_card")
        self.add_card_mock = self.ac_patcher.start()

    def tearDown(self):
        """Clean up after each test."""
        self.si_patcher.stop()
        self.ai_patcher.stop()
        self.pi_patcher.stop()
        self.aic_patcher.stop()
        self.gap_patcher.stop()
        self.gc_patcher.stop()
        self.gac_patcher.stop()
        self.ac_patcher.stop()

    @patch("compliance.notify.get_config")
    def test_notify_creates_new_issue_no_match(self, get_config_mock):
        """Test notifier creates a new issue when no match exists."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "pass_example")
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(
            kwargs,
            {"assignees": [], "labels": ["accreditation: foo", "run status: pass"]},
        )

        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_creates_new_issue_partial_match(self, get_config_mock):
        """Test notifier creates new issue when partial title match exists."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = [{"title": "x pass_example x"}]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "pass_example")
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(
            kwargs,
            {"assignees": [], "labels": ["accreditation: foo", "run status: pass"]},
        )

        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_creates_multiple_new_issues(self, get_config_mock):
        """Test notifier creates multiple GH issues when none exist."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["fail", "pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.assertEqual(self.search_issues_mock.call_count, 2)
        self.search_issues_mock.assert_any_call(
            "fail_example type:issue in:title is:open repo:foo/bar"
        )
        self.search_issues_mock.assert_any_call(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 2)
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_alerts_in_multiple_repos(self, get_config_mock):
        """Test notifier notifies in multiple repositories."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar", "bing/bong"], "status": ["pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.assertEqual(self.search_issues_mock.call_count, 2)
        self.search_issues_mock.assert_any_call(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.search_issues_mock.assert_any_call(
            "pass_example type:issue in:title is:open repo:bing/bong"
        )
        self.assertEqual(self.add_issue_mock.call_count, 2)
        foo_bar_call_args, _ = self.add_issue_mock.call_args_list[0]
        bing_bong_call_args, _ = self.add_issue_mock.call_args_list[1]
        self.assertEqual(foo_bar_call_args[0], "foo")
        self.assertEqual(foo_bar_call_args[1], "bar")
        self.assertEqual(bing_bong_call_args[0], "bing")
        self.assertEqual(bing_bong_call_args[1], "bong")

        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_adds_comment_only_to_issue(self, get_config_mock):
        """Test notifier adds a comment to an existing GH issue."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = [
            {
                "id": 1,
                "number": 123,
                "labels": [
                    {"name": "accreditation: foo", "other": "junk"},
                    {"name": "run status: pass", "other": "junk"},
                ],
                "title": "pass_example",
                "url": "123.url",
            }
        ]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.add_issue_mock.assert_not_called()
        self.patch_issue_mock.assert_not_called()
        self.assertEqual(self.add_issue_comment_mock.call_count, 1)
        args, kwargs = self.add_issue_comment_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], 123)
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(kwargs, {})

    @patch("compliance.notify.get_config")
    def test_notify_adds_label_and_comment_to_issue(self, get_config_mock):
        """Test notifier updates labels, adds comment on existing GH issue."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["pass"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = [
            {
                "id": 1,
                "number": 123,
                "labels": [
                    {"name": "accreditation: foo", "other": "junk"},
                    {"name": "run status: warn", "other": "junk"},
                ],
                "title": "pass_example",
                "url": "123.url",
            }
        ]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.add_issue_mock.assert_not_called()
        self.patch_issue_mock.assert_called_once_with(
            "foo", "bar", 123, labels=["accreditation: foo", "run status: pass"]
        )
        self.assertEqual(self.add_issue_comment_mock.call_count, 1)
        args, kwargs = self.add_issue_comment_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], 123)
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(kwargs, {})

    @patch("compliance.notify.get_config")
    def test_notify_for_new_and_old_alerts(self, get_config_mock):
        """Test notifier updates an open GH issue for a passed check."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["fail"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.side_effect = [
            [],
            [
                {
                    "id": 1,
                    "number": 123,
                    "labels": [
                        {"name": "accreditation: foo", "other": "junk"},
                        {"name": "run status: warn", "other": "junk"},
                    ],
                    "title": "pass_example",
                    "url": "123.url",
                }
            ],
        ]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.assertEqual(self.search_issues_mock.call_count, 2)
        self.search_issues_mock.assert_any_call(
            "fail_example type:issue in:title is:open repo:foo/bar"
        )
        self.search_issues_mock.assert_any_call(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "fail_example")
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(
            kwargs,
            {"assignees": [], "labels": ["accreditation: foo", "run status: fail"]},
        )
        self.patch_issue_mock.assert_called_once_with(
            "foo", "bar", 123, labels=["accreditation: foo", "run status: pass"]
        )
        self.assertEqual(self.add_issue_comment_mock.call_count, 1)
        args, kwargs = self.add_issue_comment_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], 123)
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertTrue("Run Status: **PASS" in args[3])
        self.assertEqual(kwargs, {})

    @patch("compliance.notify.get_config")
    def test_notify_old_alert_does_nothing(self, get_config_mock):
        """Test notifier does not notify for passed check w/out open issue."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {"foo": {"repo": ["foo/bar"], "status": ["fail"]}},
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.assertEqual(self.search_issues_mock.call_count, 2)
        self.search_issues_mock.assert_any_call(
            "fail_example type:issue in:title is:open repo:foo/bar"
        )
        self.search_issues_mock.assert_any_call(
            "pass_example type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "fail_example")
        self.assertTrue(args[3].startswith("## Compliance check alert"))
        self.assertEqual(
            kwargs,
            {"assignees": [], "labels": ["accreditation: foo", "run status: fail"]},
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_plain_summary_issue(self, get_config_mock):
        """Test notifier creates a new plain summary issue."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "foo-title")
        self.assertTrue(args[3].startswith("# CHECK RESULTS:"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(kwargs, {"assignees": [], "labels": []})
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_w_labels(self, get_config_mock):
        """Test notifier creates a new summary issue with labels only."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "foo-title")
        self.assertTrue(args[3].startswith("# CHECK RESULTS:"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs, {"assignees": [], "labels": ["label:foo", "foo:label"]}
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_assign(self, get_config_mock):
        """Test notifier creates a new summary issue and assigns the issue."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "assignees": ["the-dude", "walter", "donnie"],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["the-dude", "walter", "donnie"],
                "labels": ["label:foo", "foo:label"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_day_rotation_0(self, get_config_mock, datetime_mock):
        """Test new daily summary issue created and assigned to rota 0."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "day",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 31)  # Day 212

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019-07-31 - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019-07-31 - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["the-dude"],
                "labels": ["label:foo", "foo:label", "day", "2019-07-31"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_day_rotation_1(self, get_config_mock, datetime_mock):
        """Test new daily summary issue created and assigned to rota 1."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "day",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 30)  # Day 211

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019-07-30 - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019-07-30 - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["walter", "donnie"],
                "labels": ["label:foo", "foo:label", "day", "2019-07-30"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_week_rotation_0(self, get_config_mock, datetime_mock):
        """Test new weekly summary issue created and assigned to rota 0."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "week",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 25)  # Week 30

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019, 30W - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019, 30W - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["the-dude"],
                "labels": ["label:foo", "foo:label", "week", "2019", "30W"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_week_rotation_1(self, get_config_mock, datetime_mock):
        """Test new weekly summary issue created and assigned to rota 1."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "week",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 31)  # Week 31

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019, 31W - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019, 31W - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["walter", "donnie"],
                "labels": ["label:foo", "foo:label", "week", "2019", "31W"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_month_rotation_0(
        self, get_config_mock, datetime_mock
    ):
        """Test new monthly summary issue created and assigned to rota 0."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "month",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 6, 25)  # Month 6

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019, 06M - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019, 06M - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["the-dude"],
                "labels": ["label:foo", "foo:label", "month", "2019", "06M"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_month_rotation_1(
        self, get_config_mock, datetime_mock
    ):
        """Test new monthly summary issue created and assigned to rota 1."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "month",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 31)  # Month 7

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019, 07M - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019, 07M - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["walter", "donnie"],
                "labels": ["label:foo", "foo:label", "month", "2019", "07M"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_year_rotation_0(self, get_config_mock, datetime_mock):
        """Test new yearly summary issue created and assigned to rota 0."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "year",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2018, 6, 25)  # Year 2018

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2018 - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2018 - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["the-dude"],
                "labels": ["label:foo", "foo:label", "year", "2018"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.datetime")
    @patch("compliance.notify.get_config")
    def test_notify_summary_issue_year_rotation_1(self, get_config_mock, datetime_mock):
        """Test new yearly summary issue created and assigned to rota 1."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {
                        "title": "foo-title",
                        "labels": ["label:foo", "foo:label"],
                        "message": ["blah blah", "foo message"],
                        "frequency": "year",
                        "rotation": [["the-dude"], ["walter", "donnie"]],
                    },
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock
        datetime_mock.utcnow.return_value = datetime(2019, 7, 31)  # Year 2019

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.notify()
        self.search_issues_mock.assert_called_once_with(
            "2019 - foo-title type:issue in:title is:open repo:foo/bar"
        )
        self.assertEqual(self.add_issue_mock.call_count, 1)
        args, kwargs = self.add_issue_mock.call_args
        self.assertEqual(len(args), 4)
        self.assertEqual(args[0], "foo")
        self.assertEqual(args[1], "bar")
        self.assertEqual(args[2], "2019 - foo-title")
        self.assertTrue(args[3].startswith("blah blah\nfoo message\n"))
        self.assertTrue("### Passed Checks" in args[3])
        self.assertTrue("### Errored Checks" in args[3])
        self.assertTrue("### Failures/Warnings" in args[3])
        self.assertEqual(
            kwargs,
            {
                "assignees": ["walter", "donnie"],
                "labels": ["label:foo", "foo:label", "year", "2019"],
            },
        )
        self.patch_issue_mock.assert_not_called()
        self.add_issue_comment_mock.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_add_issue_to_project_no_config(self, get_config_mock):
        """Test issue is not added to project without config."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.logger.warning = MagicMock()
        notifier.notify()
        self.get_all_projects_mock.assert_not_called()
        self.get_columns_mock.assert_not_called()
        self.get_all_cards_mock.assert_not_called()
        self.add_card_mock.assert_not_called()
        notifier.logger.warning.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_add_issue_to_project_invalid_project(self, get_config_mock):
        """Test issue is not added to project without valid project config."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "project": {"invalid-project": "a-column"},
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []
        self.get_all_projects_mock.return_value = [{"id": 1, "name": "valid-project"}]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.logger.warning = MagicMock()
        notifier.notify()
        self.get_all_projects_mock.assert_called_once_with("foo/bar")
        self.get_columns_mock.assert_not_called()
        self.get_all_cards_mock.assert_not_called()
        self.add_card_mock.assert_not_called()
        notifier.logger.warning.assert_called_once_with(
            "Project invalid-project not found in foo/bar"
        )

    @patch("compliance.notify.get_config")
    def test_add_issue_to_project_invalid_column(self, get_config_mock):
        """Test issue is not added to project without valid column config."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "project": {"valid-project": "invalid-column"},
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []
        self.get_all_projects_mock.return_value = [{"id": 1, "name": "valid-project"}]
        self.get_columns_mock.return_value = [{"id": 11, "name": "valid-column"}]

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.logger.warning = MagicMock()
        notifier.notify()
        self.get_all_projects_mock.assert_called_once_with("foo/bar")
        self.get_columns_mock.assert_called_once_with(1)
        self.get_all_cards_mock.assert_not_called()
        self.add_card_mock.assert_not_called()
        notifier.logger.warning.assert_called_once_with(
            "Column invalid-column not found " "in valid-project project, foo/bar repo"
        )

    @patch("compliance.notify.get_config")
    def test_add_issue_to_project_found(self, get_config_mock):
        """Test issue is not added to project if issue already assigned."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "project": {"valid-project": "valid-column"},
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = [
            {
                "id": 1,
                "number": 123,
                "labels": [
                    {"name": "accreditation: foo", "other": "junk"},
                    {"name": "run status: pass", "other": "junk"},
                ],
                "title": "foo-title",
                "url": "123.url",
            }
        ]
        self.get_all_projects_mock.return_value = [{"id": 1, "name": "valid-project"}]
        self.get_columns_mock.return_value = [{"id": 11, "name": "valid-column"}]
        self.get_all_cards_mock.return_value = {11: [{"content_url": "123.url"}]}

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.logger.warning = MagicMock()
        notifier.notify()
        self.get_all_projects_mock.assert_called_once_with("foo/bar")
        self.get_columns_mock.assert_called_once_with(1)
        self.get_all_cards_mock.assert_called_once()
        self.add_card_mock.assert_not_called()
        notifier.logger.warning.assert_not_called()

    @patch("compliance.notify.get_config")
    def test_add_issue_to_project(self, get_config_mock):
        """Test issue is added to project when issue not yet assigned."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.side_effect = [
            {
                "accred_foo": {
                    "repo": ["foo/bar"],
                    "project": {"valid-project": "valid-column"},
                    "summary_issue": {"title": "foo-title"},
                }
            },
            "https://github.com/foo/bar",
        ]
        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["accred_foo"]
        self.search_issues_mock.return_value = []
        self.add_issue_mock.return_value = {"id": 123, "url": "123.url"}
        self.get_all_projects_mock.return_value = [{"id": 1, "name": "valid-project"}]
        self.get_columns_mock.return_value = [{"id": 11, "name": "valid-column"}]
        self.get_all_cards_mock.return_value = {11: [{"content_url": "some.other.url"}]}

        notifier = GHIssuesNotifier(self.results, controls)
        notifier.logger.warning = MagicMock()
        notifier.notify()
        self.get_all_projects_mock.assert_called_once_with("foo/bar")
        self.get_columns_mock.assert_called_once_with(1)
        self.get_all_cards_mock.assert_called_once()
        self.add_card_mock.assert_called_once_with(11, issue=123)
        notifier.logger.warning.assert_not_called()

    def _build_check_mock(self, name):
        check_mock = MagicMock()
        check_mock.test = build_compliance_check_obj(name, name, name, [name])
        return check_mock

    def _generate_result(self, status):
        return (
            f"compliance.test.{status}_example",
            {
                "status": status,
                "timestamp": time.time(),
                "test": self._build_check_mock(f"{status}_example"),
            },
        )
