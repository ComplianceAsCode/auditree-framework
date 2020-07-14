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
"""Compliance automation report builder tests module."""

import unittest
from unittest.mock import create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.controls import ControlDescriptor
from compliance.evidence import ReportEvidence
from compliance.locker import Locker
from compliance.report import ReportBuilder

from .. import build_test_mock


class ReportTest(unittest.TestCase):
    """ReportBuilder test class."""

    @patch('compliance.report.get_config')
    @patch('compliance.report.get_evidence_by_path')
    def test_report_fail_to_generate(self, evidence_path_mock, get_cfg_mock):
        """Test report generation failure affects on general execution."""
        config_mock = create_autospec(ComplianceConfig)
        config_mock.get_template_dir.return_value = '/tmp/templates'
        get_cfg_mock.return_value = config_mock

        report = ReportEvidence('test', 'test', 12345)
        report.set_content(None)
        evidence_path_mock.return_value = report

        locker = create_autospec(Locker())
        locker.local_path = '/tmp/fake_locker'

        test_obj = build_test_mock()
        test_obj.test.get_reports.return_value = ['test/example.md']

        results = {'mock.test.test_one': {'status': 'pass', 'test': test_obj}}
        controls = create_autospec(ControlDescriptor)
        builder = ReportBuilder(locker, results, controls)
        builder.build()
        self.assertEqual(results['mock.test.test_one']['status'], 'error')
