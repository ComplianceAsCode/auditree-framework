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
"""Compliance automation evidence partitioning tests module."""

import json
import unittest

from compliance.evidence import RawEvidence


class TestRawPartitionedEvidence(unittest.TestCase):
    """Test RawEvidence partitioning logic."""

    def test_is_partitioned(self):
        """Ensure is_partitioned property works as expected."""
        evidence = RawEvidence('foo.json', 'foo')
        self.assertFalse(evidence.is_partitioned)
        evidence = RawEvidence(
            'foo.json', 'foo', partition={'fields': ['foo']}
        )
        self.assertTrue(evidence.is_partitioned)
        evidence = RawEvidence('foo.txt', 'foo', partition={'fields': ['foo']})
        self.assertFalse(evidence.is_partitioned)

    def test_partition_keys_default_root(self):
        """Ensure keys returned for default root."""
        evidence = RawEvidence(
            'foo.json', 'foo', partition={'fields': ['foo', 'bar']}
        )
        evidence.set_content(
            json.dumps(
                [
                    {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                    }, {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                    }, {
                        'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                    }
                ]
            )
        )
        keys = evidence.partition_keys
        self.assertEqual(len(keys), 2)
        self.assertTrue(['FOO', 'BAR'] in keys)
        self.assertTrue(['FOO', 'BOO'] in keys)

    def test_partition_keys_root(self):
        """Ensure keys returned for a defined root."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['foo', 'bar'], 'root': 'root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'root': [
                        {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                        }, {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                        }, {
                            'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                        }
                    ],
                    'other_stuff': 'so what?'
                }
            )
        )
        keys = evidence.partition_keys
        self.assertEqual(len(keys), 2)
        self.assertTrue(['FOO', 'BAR'] in keys)
        self.assertTrue(['FOO', 'BOO'] in keys)

    def test_partition_keys_nested_root(self):
        """Ensure keys returned for a defined nested root."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['foo', 'bar'], 'root': 'nested.root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'nested': {
                        'nested_stuff': 'who cares?',
                        'root': [
                            {
                                'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                            }, {
                                'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                            }, {
                                'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                            }
                        ],
                        'nested_other_stuff': 'so what?'
                    },
                    'other_stuff': 'so what?'
                }
            )
        )
        keys = evidence.partition_keys
        self.assertEqual(len(keys), 2)
        self.assertTrue(['FOO', 'BAR'] in keys)
        self.assertTrue(['FOO', 'BOO'] in keys)

    def test_partition_keys_dot_notation(self):
        """Ensure keys returned when using dot notation for key fields."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['dot_nota.foo', 'dot_nota.bar'],
                'root': 'nested.root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'nested': {
                        'nested_stuff': 'who cares?',
                        'root': [
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BAR'
                                },
                                'baz': 'BAZ'
                            },
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BAR'
                                },
                                'baz': 'BLAH'
                            },
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BOO'
                                },
                                'baz': 'BAZ'
                            }
                        ],
                        'nested_other_stuff': 'so what?'
                    },
                    'other_stuff': 'so what?'
                }
            )
        )
        keys = evidence.partition_keys
        self.assertEqual(len(keys), 2)
        self.assertTrue(['FOO', 'BAR'] in keys)
        self.assertTrue(['FOO', 'BOO'] in keys)

    def test_get_partition_default_root(self):
        """Ensure partition returned for default root."""
        evidence = RawEvidence(
            'foo.json', 'foo', partition={'fields': ['foo', 'bar']}
        )
        evidence.set_content(
            json.dumps(
                [
                    {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                    }, {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                    }, {
                        'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                    }
                ]
            )
        )
        self.assertEqual(
            json.loads(evidence.get_partition(['FOO', 'BAR'])),
            [
                {
                    'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                }, {
                    'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                }
            ]
        )

    def test_get_partition_with_root(self):
        """Ensure partition returned for a defined root."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['foo', 'bar'], 'root': 'root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'root': [
                        {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                        }, {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                        }, {
                            'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                        }
                    ],
                    'other_stuff': 'so what?'
                }
            )
        )
        self.assertEqual(
            json.loads(evidence.get_partition(['FOO', 'BAR'])),
            {
                'stuff': 'who cares?',
                'root': [
                    {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                    }, {
                        'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                    }
                ],
                'other_stuff': 'so what?'
            }
        )

    def test_get_partition_with_nested_root(self):
        """Ensure partition returned for a defined nested root."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['foo', 'bar'], 'root': 'nested.root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'nested': {
                        'nested_stuff': 'who cares?',
                        'root': [
                            {
                                'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                            }, {
                                'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                            }, {
                                'foo': 'FOO', 'bar': 'BOO', 'baz': 'BAZ'
                            }
                        ],
                        'nested_other_stuff': 'so what?'
                    },
                    'other_stuff': 'so what?'
                }
            )
        )
        self.assertEqual(
            json.loads(evidence.get_partition(['FOO', 'BAR'])),
            {
                'stuff': 'who cares?',
                'nested': {
                    'nested_stuff': 'who cares?',
                    'root': [
                        {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BAZ'
                        }, {
                            'foo': 'FOO', 'bar': 'BAR', 'baz': 'BLAH'
                        }
                    ],
                    'nested_other_stuff': 'so what?'
                },
                'other_stuff': 'so what?'
            }
        )

    def test_get_partition_using_dot_notation(self):
        """Ensure partition returned when using dot notation for key fields."""
        evidence = RawEvidence(
            'foo.json',
            'foo',
            partition={
                'fields': ['dot_nota.foo', 'dot_nota.bar'],
                'root': 'nested.root'
            }
        )
        evidence.set_content(
            json.dumps(
                {
                    'stuff': 'who cares?',
                    'nested': {
                        'nested_stuff': 'who cares?',
                        'root': [
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BAR'
                                },
                                'baz': 'BAZ'
                            },
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BAR'
                                },
                                'baz': 'BLAH'
                            },
                            {
                                'dot_nota': {
                                    'foo': 'FOO', 'bar': 'BOO'
                                },
                                'baz': 'BAZ'
                            }
                        ],
                        'nested_other_stuff': 'so what?'
                    },
                    'other_stuff': 'so what?'
                }
            )
        )
        self.assertEqual(
            json.loads(evidence.get_partition(['FOO', 'BAR'])),
            {
                'stuff': 'who cares?',
                'nested': {
                    'nested_stuff': 'who cares?',
                    'root': [
                        {
                            'dot_nota': {
                                'foo': 'FOO', 'bar': 'BAR'
                            },
                            'baz': 'BAZ'
                        },
                        {
                            'dot_nota': {
                                'foo': 'FOO', 'bar': 'BAR'
                            },
                            'baz': 'BLAH'
                        }
                    ],
                    'nested_other_stuff': 'so what?'
                },
                'other_stuff': 'so what?'
            }
        )
