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
"""Compliance automation PagerDuty notifier tests module."""

import unittest
from unittest.mock import create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import PagerDutyNotifier

from .. import build_test_mock


class PagerDutyNotifierTest(unittest.TestCase):
    """PagerDutyNotifier test class."""

    @patch("compliance.notify.pagerduty.get")
    @patch("compliance.notify.pagerduty.send_event")
    @patch("compliance.notify.get_config")
    def test_notify_with_runbooks(self, get_config_mock, pd_send_mock, pd_get_mock):
        """Test that PagerDutyNotifier notifications have runbook links."""
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
        notifier = PagerDutyNotifier(results, controls)
        notifier.notify()

        self.assertTrue(pd_get_mock.called)
        self.assertTrue(pd_send_mock.called)

        args, kwargs = pd_send_mock.call_args

        for link in kwargs["links"]:
            if link["text"] == "Runbook":
                self.assertIn("http://mockedrunbooks/path/to", link["href"])

    @patch("compliance.notify.pagerduty.get")
    @patch("compliance.notify.pagerduty.send_event")
    @patch("compliance.notify.get_config")
    def test_notify_without_runbooks(self, get_config_mock, pd_send_mock, pd_get_mock):
        """Test that PagerDutyNotifier notifications have no runbook links."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {"infra": ["#channel"]}

        get_config_mock.return_value = config_mock

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ["infra"]

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

        notifier = PagerDutyNotifier(results, controls)
        notifier.notify()

        self.assertTrue(pd_get_mock.called)
        self.assertTrue(pd_send_mock.called)

        args, kwargs = pd_send_mock.call_args

        self.assertEqual(0, len(kwargs["links"]))
