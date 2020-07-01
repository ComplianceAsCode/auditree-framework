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
"""Compliance automation fetcher helper methods tests module."""

import os
import tempfile

from compliance.evidence import RawEvidence
from compliance.fetch import ComplianceFetcher, fetch

from nose.tools import assert_equals, with_setup

LOGO_PATH = os.path.join(tempfile.gettempdir(), 'logo.svg')


def clean_tmp():
    """Clean up the tmp directory."""
    os.remove(LOGO_PATH)


@with_setup(teardown=clean_tmp)
def _test_fetch():
    """Test basic fetch from public site."""
    assert_equals(
        fetch(
            'https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg',
            'logo.svg'
        ),
        LOGO_PATH
    )
    os.remove(LOGO_PATH)


class TestFetcher(ComplianceFetcher):
    """ComplianceFetcher helper methods test class."""

    def _test_fetch_url(self):
        """Test Compliance Fetcher - fetcher URL."""
        RawEvidence(
            'logo.svg',
            'test_category',
            24 * 60 * 60,
            'This test reports fetch.py'
        )
        url = (
            'https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg'
        )
        content = self.fetchCloudantDoc(url)
        self.assertIsNot(content, None)
