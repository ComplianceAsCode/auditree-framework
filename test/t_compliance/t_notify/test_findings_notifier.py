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
"""Compliance automation findings notifier tests module."""

import time
import unittest
from unittest import mock
from unittest.mock import MagicMock, Mock, create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.notify import FindingsNotifier

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

from ibm_security_advisor_findings_api_sdk import ApiException

from requests.models import Response

from .. import build_compliance_check_obj


class FindingsNotifierTest(unittest.TestCase):
    """FindingsNotifier test class."""

    def setUp(self):
        """Initialize each test."""
        self.results = {}
        for status in ['pass', 'fail', 'error', 'warn']:
            name, result = self._generate_result(status)
            self.results[name] = result
        note_name = 'account_id/providers/provider_id/notes/note_id'
        self.data = {
            'occurrence_list': [
                {
                    'id': 'test-id',
                    'kind': 'FINDING',
                    'note_name': note_name,
                    'context': {
                        'region': 'region',
                        'resource_id': 'resource_id',
                        'resource_type': 'resource_type',
                        'resource_name': 'resource_name',
                        'service_name': 'Auditree',
                    },
                    'finding': {
                        'severity': 'severity'
                    }
                }
            ],
            'account_id': 'account_id',
            'provider_id': 'provider_id'
        }

    @patch('compliance.notify.get_config')
    @patch('compliance.notify.IAMAuthenticator')
    def test_notify_findings_success(self, get_config_mock, iam_mock):
        """Test Findings notifier sends content to SA findings."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'audit': 'https://localhost'}
        get_config_mock.return_value = config_mock
        controls_mock = create_autospec(ControlDescriptor)
        controls_mock.get_accreditations.return_value = ['audit']
        iam_mock = create_autospec(IAMAuthenticator)
        iam_mock.validate.return_value = True
        with mock.patch('compliance.notify.FindingsApiV1') as findings_mock:
            the_response = Mock(spec=Response)
            the_response.json.return_value = {}
            the_response.status_code = 200
            mock_findings = findings_mock.return_value
            mock_findings.create_occurrence.return_value = the_response
            notifier = FindingsNotifier(self.results, controls_mock)
            notifier.notify()
            result = notifier._create_findings(self.data)

            self.assertEqual(result, 0)

    @patch('compliance.notify.get_config')
    @patch('compliance.notify.IAMAuthenticator')
    def test_notify_findings_409_exception(self, get_config_mock, iam_mock):
        """Test Findings notifier handles 409 conflicts."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'audit': 'https://localhost'}
        get_config_mock.return_value = config_mock
        controls_mock = create_autospec(ControlDescriptor)
        controls_mock.get_accreditations.return_value = ['audit']
        iam_mock = create_autospec(IAMAuthenticator)
        iam_mock.validate.return_value = True
        with mock.patch('compliance.notify.FindingsApiV1') as findings_mock:
            mock_findings = findings_mock.return_value
            mock_findings.create_occurrence.side_effect = ApiException(
                code=409
            )
            notifier = FindingsNotifier(self.results, controls_mock)
            notifier.notify()
            result = notifier._create_findings(self.data)

            self.assertEqual(result, 409)

    @patch('compliance.notify.get_config')
    @patch('compliance.notify.IAMAuthenticator')
    def test_notify_findings_unexpected_error(self, get_config_mock, iam_mock):
        """Test Findings notifier handles unexpected errors."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get.return_value = {'audit': 'https://localhost'}
        get_config_mock.return_value = config_mock
        controls_mock = create_autospec(ControlDescriptor)
        controls_mock.get_accreditations.return_value = ['audit']
        iam_mock = create_autospec(IAMAuthenticator)
        iam_mock.validate.return_value = True
        with mock.patch('compliance.notify.FindingsApiV1') as findings_mock:
            mock_findings = findings_mock.return_value
            mock_findings.create_occurrence.side_effect = Exception(
                {'status_code': 500}
            )
            notifier = FindingsNotifier(self.results, controls_mock)
            notifier.notify()
            result = notifier._create_findings(self.data)

            self.assertEqual(result, -1)

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
