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
"""Compliance automation control descriptor tests module."""

import unittest

from compliance.controls import ControlDescriptor


class ControlDescriptorTest(unittest.TestCase):
    """ControlDescriptor test class."""

    def setUp(self):
        """Initialize each test."""
        cd_paths = [
            './test/fixtures/controls/original',
            './test/fixtures/controls/simplified',
            './faker'
        ]
        self.cd = ControlDescriptor(cd_paths)
        self.expected_foo_check = 'foo_pkg.checks.test_foo_module.FooCheck'
        self.expected_bar_check = 'bar_pkg.checks.test_bar_module.BarCheck'

    def test_contructor_and_base_properties(self):
        """Check ControlDescriptor constructed as expected."""
        self.assertEqual(len(self.cd.paths), 2)
        expected_ends_with = [
            '/test/fixtures/controls/original/controls.json',
            '/test/fixtures/controls/simplified/controls.json'
        ]
        self.assertNotEqual(self.cd.paths[0], expected_ends_with[0])
        self.assertTrue(self.cd.paths[0].endswith(expected_ends_with[0]))
        self.assertNotEqual(self.cd.paths[1], expected_ends_with[1])
        self.assertTrue(self.cd.paths[1].endswith(expected_ends_with[1]))
        self.assertEqual(
            self.cd.as_dict,
            {
                self.expected_foo_check: {
                    'foo_evidence': {
                        'foo_control': ['accred.foo']
                    }
                },
                self.expected_bar_check: ['accred.bar']
            }
        )

    def test_as_dict_immutability(self):
        """Ensure that control content cannot be changed through as_dict."""
        with self.assertRaises(AttributeError) as ar:
            self.cd.as_dict = {'foo': 'bar'}
        self.assertEqual(str(ar.exception), "can't set attribute")
        controls_copy = self.cd.as_dict
        self.assertEqual(controls_copy, self.cd.as_dict)
        controls_copy.update({'foo': 'bar'})
        self.assertNotEqual(controls_copy, self.cd.as_dict)

    def test_accred_checks(self):
        """Check that checks are organized by accreditations correctly."""
        self.assertEqual(
            self.cd.accred_checks,
            {
                'accred.foo': {self.expected_foo_check},
                'accred.bar': {self.expected_bar_check}
            }
        )

    def test_get_accreditations(self):
        """Ensure the correct accreditations are returned based on check."""
        self.assertEqual(
            self.cd.get_accreditations(self.expected_foo_check),
            {'accred.foo'}
        )
        self.assertEqual(
            self.cd.get_accreditations(self.expected_bar_check),
            {'accred.bar'}
        )

    def test_is_test_included(self):
        """Test check is included in accreditations functionality."""
        self.assertTrue(
            self.cd.is_test_included(self.expected_foo_check, ['accred.foo'])
        )
        self.assertFalse(
            self.cd.is_test_included(self.expected_foo_check, ['accred.bar'])
        )
        self.assertTrue(
            self.cd.is_test_included(self.expected_bar_check, ['accred.bar'])
        )
        self.assertFalse(
            self.cd.is_test_included(self.expected_bar_check, ['accred.foo'])
        )
        self.assertTrue(
            self.cd.is_test_included(
                self.expected_foo_check, ['accred.foo', 'accred.bar']
            )
        )
        self.assertTrue(
            self.cd.is_test_included(
                self.expected_bar_check, ['accred.foo', 'accred.bar']
            )
        )
        self.assertFalse(
            self.cd.is_test_included(self.expected_foo_check, ['accred.baz'])
        )
