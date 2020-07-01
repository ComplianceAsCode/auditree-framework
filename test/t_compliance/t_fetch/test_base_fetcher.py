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
"""Compliance automation fetcher base tests module."""

import unittest

from compliance.config import ComplianceConfig
from compliance.fetch import ComplianceFetcher


class ComplianceFetchTest(unittest.TestCase):
    """ComplianceFetcher base test class."""

    def setUp(self):
        """Initialize each test."""
        # Since unittest.TestCase needs a method for running the test
        # (runTest, by default) and ComplianceFetcher is a child of
        # unittest.TestCase, we must pass a method in the
        # constructor (otherwise, we will get a ValueError). Since we
        # don't need this method, passing ``__doc__`` is enough for
        # building a ComplianceCheck object successfully.
        self.check = ComplianceFetcher('__doc__')

    def test_config(self):
        """Check that the config property returns a ComplianceConfig object."""
        self.assertIsInstance(self.check.config, ComplianceConfig)
