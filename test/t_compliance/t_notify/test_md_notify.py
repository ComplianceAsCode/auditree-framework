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
"""Compliance automation base markdown notifier tests module."""

import unittest
from unittest.mock import create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import _BaseMDNotifier

from .. import build_test_mock


class BaseNotifierTest(unittest.TestCase):
    """Base notifier test class."""

    @patch('compliance.notify.get_config')
    def test_notify_with_runbooks(self, get_config_mock):
        """Test that _BaseMDNotifier notifications have runbook links."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'infra': ['#channel']}

        get_config_mock.return_value = config_mock

        results = {
            'compliance.test.runbook': {
                'status': 'warn', 'test': build_test_mock(fails=1)
            },
            'compliance.test.other_runbook': {
                'status': 'fail', 'test': build_test_mock('two', warns=1)
            }
        }

        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra']
        notifier = _BaseMDNotifier(results, controls)

        split_tests = notifier._split_by_status(notifier.messages)

        results_by_status = {
            'pass': split_tests[0],
            'fail': split_tests[1],
            'warn': split_tests[2],
            'error': split_tests[3]
        }

        markdown = '\n'.join(
            notifier._generate_accred_content('unittests', results_by_status)
        )

        self.assertIn(
            ' | [Run Book](http://mockedrunbooks/path/to/runbook_one)',
            markdown
        )
        self.assertIn(
            ' | [Run Book](http://mockedrunbooks/path/to/runbook_two)',
            markdown
        )
