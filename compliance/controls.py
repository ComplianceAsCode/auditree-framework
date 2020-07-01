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
"""Compliance check controls automation module."""

import copy
import itertools
import json
import os


class ControlDescriptor(object):
    """
    Class abstraction for controls.json content.

    Used when processing controls.json content.
    """

    def __init__(self, dirs=None):
        """Construct and initialize the ControlDescriptor object."""
        dirs = dirs or [os.path.abspath('.')]
        self._controls = {}
        self._paths = []
        for d in dirs:
            json_file = os.path.join(d, 'controls.json')
            if not os.path.isfile(json_file):
                continue
            self._controls.update(json.loads(open(json_file).read()))
        self._paths.append(json_file)

    @property
    def paths(self):
        """All absolute paths to ``controls.json`` file(s)."""
        return self._paths

    @property
    def as_dict(self):
        """Provide control descriptor content as a modifiable dictionary."""
        return copy.deepcopy(self._controls)

    def get_accreditations(self, test_path):
        """
        Provide the accreditation list for a given test_path.

        :param test_path: the Python path to the test. For instance:
          ``package.accr1.TestClass`` or ``package.accr2.test_function``
        """
        test_paths = self._controls.get(test_path, {})
        accreditations = [
            itertools.chain(*c.values()) for c in test_paths.values()
        ]
        return set(itertools.chain(*accreditations))

    def is_test_included(self, test_path, accreditations):
        """
        Provide boolean result of whether a check is part of accreditations.

        :param test_path: the Python path to the test. For instance:
          ``package.accr1.TestClass`` or ``package.accr2.test_function``
        :param accreditations: list of accreditations names where ``test_path``
          may be included.
        """
        current_accreditations = self.get_accreditations(test_path)
        matched = set(accreditations).intersection(set(current_accreditations))
        return len(matched) != 0
