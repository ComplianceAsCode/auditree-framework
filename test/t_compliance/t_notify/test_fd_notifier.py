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
"""Compliance automation file descriptor notifier tests module."""

import unittest
from io import StringIO
from unittest.mock import create_autospec

from compliance.controls import ControlDescriptor
from compliance.notify import FDNotifier

from .. import build_test_mock


class FDNotifierTest(unittest.TestCase):
    """FDNotifier test class."""

    def setUp(self):
        """Initialize each test."""
        self.fd = StringIO()

    def test_notify_with_no_results(self):
        """Check that FDNotifier notifies that there are no results."""
        notifier = FDNotifier({}, {}, self.fd)
        notifier.notify()
        self.assertEqual(
            self.fd.getvalue(), '\n-- NOTIFICATIONS --\n\nNo results\n'
        )

    def test_notify_normal_run(self):
        """Check that FDNotifier notifies a test with Error."""
        results = {
            'compliance.test.one': {
                'status': 'error', 'test': build_test_mock()
            },
            'compliance.test.two': {
                'status': 'warn', 'test': build_test_mock('two', warns=1)
            },
            'compliance.test.three': {
                'status': 'fail', 'test': build_test_mock('three', fails=1)
            },
            'compliance.test.four': {
                'status': 'pass', 'test': build_test_mock('four')
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra-internal']
        notifier = FDNotifier(results, controls, self.fd)
        notifier.notify()
        self.assertIn(
            (
                '\n-- NOTIFICATIONS --\n\n'
                'Notifications for INFRA-INTERNAL accreditation'
            ),
            self.fd.getvalue()
        )
        self.assertIn(
            (
                'mock check title one - ERROR () Reports: (none) '
                '| <http://mockedrunbooks/path/to/runbook_one|Run Book>\n'
                'Check compliance.test.one failed to execute'
            ),
            self.fd.getvalue()
        )
        self.assertIn(
            (
                'mock check title two - WARN (1 warnings) Reports: (none) '
                '| <http://mockedrunbooks/path/to/runbook_two|Run Book>'
            ),
            self.fd.getvalue()
        )
        self.assertIn(
            (
                'mock check title three - FAIL (1 failures) Reports: (none) '
                '| <http://mockedrunbooks/path/to/runbook_three|Run Book>'
            ),
            self.fd.getvalue()
        )
        self.assertIn(
            'PASSED checks: mock check title four', self.fd.getvalue()
        )

    def test_notify_push_error(self):
        """Check that FDNotifier notifies a test with Error."""
        results = {
            'compliance.test.one': {
                'status': 'error', 'test': build_test_mock()
            },
            'compliance.test.two': {
                'status': 'warn', 'test': build_test_mock('two', warns=1)
            },
            'compliance.test.three': {
                'status': 'fail', 'test': build_test_mock('three', fails=1)
            },
            'compliance.test.four': {
                'status': 'pass', 'test': build_test_mock('four')
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra-internal']
        notifier = FDNotifier(results, controls, self.fd, push_error=True)
        notifier.notify()
        self.assertEqual(
            (
                '\n-- NOTIFICATIONS --\n\n'
                'All accreditation checks:  '
                'Evidence/Results failed to push to remote locker.\n'
            ),
            self.fd.getvalue()
        )
