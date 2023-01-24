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
"""Compliance automation utilities tests module."""

import hashlib
import unittest

from compliance.utils.data_parse import get_sha256_hash


class TestUtilityFunctions(unittest.TestCase):
    """Test data_parse utility functions."""

    def test_sha256_hash_no_size(self):
        """Test when no size is provided, the full hash is returned."""
        self.assertEqual(
            get_sha256_hash(['foo']), hashlib.sha256(b'foo').hexdigest()
        )

    def test_sha256_hash_oversized(self):
        """Test when size is too big, the full hash is returned."""
        expected = hashlib.sha256(b'foo').hexdigest()
        self.assertEqual(len(expected), 64)
        self.assertEqual(get_sha256_hash(['foo'], 1000), expected)

    def test_sha256_hash_sized(self):
        """Test the first 'size' number of characters are returned."""
        actual = get_sha256_hash(['foo'], 10)
        self.assertEqual(len(actual), 10)
        self.assertTrue(hashlib.sha256(b'foo').hexdigest().startswith(actual))

    def test_sha256_hash_multiple_keys(self):
        """Test hash is correct when a list of keys is provided."""
        self.assertEqual(
            get_sha256_hash(['foo', 'bar', 'baz', 1234]),
            hashlib.sha256(b'foobarbaz1234').hexdigest()
        )
