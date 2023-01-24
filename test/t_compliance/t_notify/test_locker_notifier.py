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
"""Compliance automation Locker notifier tests module."""

import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, create_autospec, patch

from compliance.controls import ControlDescriptor
from compliance.locker import Locker
from compliance.notify import LockerNotifier

from .. import build_compliance_check_obj


class LockerNotifierTest(unittest.TestCase):
    """LockerNotifier test class."""

    def setUp(self):
        """Initialize each test."""
        self.results = {}
        for status in ['pass', 'fail', 'error', 'warn']:
            name, result = self._generate_result(status)
            self.results[name] = result

    @patch('compliance.notify.datetime')
    def test_notify_sends_content_to_locker(self, datetime_mock):
        """Test locker notifier sends content to locker as expected."""
        controls_mock = create_autospec(ControlDescriptor)
        controls_mock.get_accreditations.return_value = ['foo']
        locker_mock = create_autospec(Locker)
        datetime_mock.utcnow.return_value = datetime(2019, 10, 14)

        notifier = LockerNotifier(self.results, controls_mock, locker_mock)
        notifier.notify()

        self.assertEqual(locker_mock.add_content_to_locker.call_count, 1)
        args, kwargs = locker_mock.add_content_to_locker.call_args
        self.assertEqual(len(args), 3)
        self.assertEqual(kwargs, {})
        self.assertTrue(
            args[0].startswith('# CHECK RESULTS: 2019-10-14 00:00:00')
        )
        self.assertTrue('## Notification for FOO accreditation' in args[0])
        self.assertTrue('### Passed Checks' in args[0])
        self.assertTrue('### Errored Checks' in args[0])
        self.assertTrue('### Failures/Warnings' in args[0])
        self.assertEqual(args[1], 'notifications')
        self.assertEqual(args[2], 'alerts_summary.md')

    def _build_check_mock(self, name):
        check_mock = MagicMock()
        check_mock.test = build_compliance_check_obj(name, name, name, [name])
        return check_mock

    def _generate_result(self, status):
        return (
            f'compliance.test.{status}_example',
            {
                'status': status,
                'timestamp': time.time(),
                'test': self._build_check_mock(f'{status}_example')
            }
        )
