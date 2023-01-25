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
"""Compliance automation Slack notifier tests module."""

import json
import unittest
try:
    from mock import patch, create_autospec
except ImportError:
    from unittest.mock import patch, create_autospec

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import SlackNotifier

from .. import build_test_mock


class SlackNotifierTest(unittest.TestCase):
    """SlackNotifier test class."""

    @patch('requests.post')
    @patch('compliance.notify.get_config')
    def test_notify_error(self, get_config_mock, post_mock):
        """Test that SlackNotifier notifies a test with Error."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'infra': ['#channel']}
        get_config_mock.return_value = config_mock

        results = {
            'compliance.test.example': {
                'status': 'error', 'test': build_test_mock()
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra']
        notifier = SlackNotifier(results, controls)
        notifier.notify()
        self.assertTrue(post_mock.called)

        args, kwargs = post_mock.call_args
        self.assertTrue(args[0].startswith('https://hooks.slack.com'))
        msg = json.loads(kwargs['data'])
        self.assertIn('failed to execute', msg['attachments'][0]['text'])

    @patch('requests.post')
    @patch('compliance.notify.get_config')
    def test_notify_two_errors(self, get_config_mock, post_mock):
        """Test that SlackNotifier notifies two tests with Error."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'infra': ['#channel']}
        get_config_mock.return_value = config_mock

        results = {
            'compliance.test.example': {
                'status': 'error', 'test': build_test_mock()
            },
            'compliance.test.other_example': {
                'status': 'error', 'test': build_test_mock('two')
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra']
        notifier = SlackNotifier(results, controls)
        notifier.notify()

        self.assertTrue(post_mock.called)
        args, kwargs = post_mock.call_args
        self.assertTrue(args[0].startswith('https://hooks.slack.com'))
        msg = json.loads(kwargs['data'])
        self.assertEqual(len(msg['attachments']), 3)
        self.assertEqual('PASSED checks', msg['attachments'][2]['title'])
        for att in msg['attachments'][:-1]:
            self.assertIn('failed to execute', att['text'])

    @patch('requests.post')
    @patch('compliance.notify.get_config')
    def test_do_not_notify_if_unknown_acc(self, get_config_mock, post_mock):
        """Test that SlackNotifier does not notify if accred is unknown."""
        results = {
            'compliance.test.example': {
                'status': 'error', 'test': build_test_mock()
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['SOMETHING-WRONG']
        notifier = SlackNotifier(results, controls)
        notifier.notify()
        post_mock.assert_not_called()

    @patch('requests.post')
    @patch('compliance.notify.get_config')
    def test_notify_with_runbooks(self, get_config_mock, post_mock):
        """Test that SlackNotifier notifications have runbook links."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'infra': ['#channel']}

        get_config_mock.return_value = config_mock

        results = {
            'compliance.test.runbook': {
                'status': 'error', 'test': build_test_mock()
            },
            'compliance.test.other_runbook': {
                'status': 'error', 'test': build_test_mock('two')
            }
        }
        controls = create_autospec(ControlDescriptor)
        controls.get_accreditations.return_value = ['infra']
        notifier = SlackNotifier(results, controls)
        notifier.notify()

        self.assertTrue(post_mock.called)
        args, kwargs = post_mock.call_args
        self.assertTrue(args[0].startswith('https://hooks.slack.com'))
        msg = json.loads(kwargs['data'])
        self.assertEqual(len(msg['attachments']), 3)
        self.assertEqual('PASSED checks', msg['attachments'][2]['title'])
        for att in msg['attachments'][:-1]:
            testname = att['title'].rsplit(' ', 1)[1]
            url = f'http://mockedrunbooks/path/to/runbook_{testname}'
            notifier.logger.warning(testname)
            notifier.logger.warning(url)
            self.assertIn(f' | <{url}|Run Book>', att['text'])
