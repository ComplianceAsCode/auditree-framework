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
"""Compliance automation data and formatting utilities module."""

import hashlib
import json


def parse_dot_key(data, key):
    """
    Provide the element from the ``data`` dictionary defined by the ``key``.

    The key may be a key path depicted by dot notation.

    :param data: A dictionary
    :param key: A dictionary key string that may be a key path depicted by dot
      notation. For example "foo.bar".

    :returns: The dictionary value from ``data`` associated to the ``key``.
    """
    for key_part in key.split("."):
        data = data.get(key_part)
        if data is None:
            break
    return data


def get_sha256_hash(key, size=None):
    """
    Provide a SHA256 hash based on the supplied key values.

    :param key: An iterable of key values.
    :param size: The size of the returned hash.  Defaults to full hash.  If
      size provided is greater than the hash size the full hash is returned.

    :returns: a SHA256 hash for the key values supplied.
    """
    partition_hash = hashlib.sha256()
    for part in key:
        partition_hash.update(str(part).encode("utf-8"))
    sha256_hash = partition_hash.hexdigest()
    if not size or size > len(sha256_hash):
        size = len(sha256_hash)
    return sha256_hash[:size]


def format_json(data, **addl_kwargs):
    """
    Provide a JSON string formatted to the standards of the library.

    This function ensures that the JSON is sorted, indented, and uses
    the appropriate separators for all instances of JSON generated
    by this library.

    :param data: The data structure to be formatted.
    :param add_kwargs: Additional json.dumps options

    :returns: A formatted JSON string.
    """
    return json.dumps(
        data, indent=2, sort_keys=True, separators=(",", ": "), **addl_kwargs
    )


def deep_merge(a, b, path=None, append=False):
    r"""
    Merge two dicts, taking into account any sub (or sub-sub-\*) dicts.

    If ``append`` is ``True`` then list values from ``b`` will be appended to
    ``a``'s.  Modified from: https://stackoverflow.com/a/7205107/566346
    """
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                deep_merge(a[key], b[key], (path or []) + [str(key)], append)
                continue
            is_lists = isinstance(a[key], list) and isinstance(b[key], list)
            if is_lists and append:
                a[key] += b[key]
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a
