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
"""Compliance automation underlying test framework utilities module."""


def parse_test_id(test_id):
    """
    Parse a test ID into useful parts.

    Takes a test ID and parses out useful parts of it::

        > parse_test_id(
            'cloudant.checks.infra.test_user_audit_softlayer.'
            'UserAuditSoftLayer.test_users')
        {
            'scope': 'cloudant',
            'type': 'checks',
            'accreditation': 'infra',
            'file': 'test_user_audit_softlayer',
            'class': 'UserAuditSoftLayer',
            'method': 'test_users',
            'class_path': (
                'cloudant.checks.infra.'
                'test_user_audit_softlayer.UserAuditSoftLayer')
        }

    Note: scope/type/accreditation might not be returned if your
    path structure is different from the suggested one.
    """
    parts = test_id.split('.')
    full_path = len(parts) == 6
    return {
        'scope': full_path and parts[0],
        'type': full_path and parts[1],
        'accreditation': full_path and parts[2],
        'file': parts[-3],
        'class': parts[-2],
        'method': parts[-1],
        'class_path': '.'.join(parts[0:-1])
    }
