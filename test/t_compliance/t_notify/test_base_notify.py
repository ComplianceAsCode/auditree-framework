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
"""Compliance automation notifier base tests module."""

import unittest
from unittest.mock import create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import _BaseNotifier

from .. import build_test_mock


class BaseNotifierTest(unittest.TestCase):
    """Base notifier test class."""

    def _test_url(self, test_desc, msg, notifier, expected=True):
        test_name = str(test_desc["test"].test).split("_", 1)[1]
        summary, addl_content = notifier._get_summary_and_body(test_desc, msg)
        test_url = f"http://mockedrunbooks/path/to/runbook_{test_name}"
        if expected:
            self.assertIn(f" | <{test_url}|Run Book>", summary)
        else:
            self.assertNotIn(f" | <{test_url}|Run Book>", summary)

    @patch("compliance.notify.get_config")
    def test_notify_with_runbooks(self, get_config_mock):
        """Check that _BaseNotifier notifications have runbook links."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {"infra": ["#channel"]}

        get_config_mock.return_value = config_mock

        results = {
            "compliance.test.runbook": {"status": "error", "test": build_test_mock()},
            "compliance.test.other_runbook": {
                "status": "error",
                "test": build_test_mock("two"),
            },
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["infra"]
        notifier = _BaseNotifier(results, controls, push_error=False)

        (_, _, _, errored_tests) = notifier._split_by_status(notifier.messages)

        for _, test_desc, msg in errored_tests:
            self._test_url(test_desc, msg, notifier, expected=True)

    @patch("compliance.notify.get_config")
    def test_notify_without_runbooks(self, get_config_mock):
        """Check that _BaseNotifier notifications have no runbook links."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {
            "infra": ["#channel"],
            "runbooks": {"base_url": "http://myrunbooks.io"},
        }

        get_config_mock.return_value = config_mock

        results = {
            "compliance.test.runbook": {
                "status": "error",
                "test": build_test_mock(baseurl=""),
            },
            "compliance.test.other_runbook": {
                "status": "error",
                "test": build_test_mock("two", baseurl=""),
            },
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["infra"]
        notifier = _BaseNotifier(results, controls, push_error=False)

        (_, _, _, errored_tests) = notifier._split_by_status(notifier.messages)

        for _, test_desc, msg in errored_tests:
            self._test_url(test_desc, msg, notifier, expected=False)
