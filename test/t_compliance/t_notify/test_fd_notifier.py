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
        """Check that FDNotifier does not notify if no results."""
        notifier = FDNotifier({}, {}, self.fd)
        notifier.notify()
        self.assertEquals(self.fd.getvalue(), '')

    def test_notify_error(self):
        """Check that FDNotifier notifies a test with Error."""
        results = {
            'compliance.test.example': {
                'status': 'error', 'test': build_test_mock()
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra-internal']
        notifier = FDNotifier(results, controls, self.fd)
        notifier.notify()
        self.assertIn('INFRA-INTERNAL', self.fd.getvalue())
