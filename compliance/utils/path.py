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
"""Compliance automation path formatting utilities module."""

import imp
import os
import sys

from compliance.config import get_config

FETCH_PREFIX = 'fetch_'
CHECK_PREFIX = 'test_'


def get_toplevel_dirpath(path):
    """
    Provide the toplevel directory for the given path.

    The toplevel directory will be the one containing ``controls.json`` file.
    This function returns ``None`` if toplevel path could not be calculated.

    :param path: absolute or relative path to file or dir.
    """
    if path == '/' or path is None:
        return None
    if os.path.exists(os.path.join(path, 'controls.json')):
        return path
    return get_toplevel_dirpath(os.path.dirname(path))


def load_evidences_modules(toplevel):
    """
    Load the all evidences modules found at toplevel directory.

    This function prevents double loading.

    :param toplevel: path to the toplevel directory.
    """
    for root, dirs, _ in os.walk(toplevel):
        for d in dirs:
            try:
                mod_data = imp.find_module(
                    'evidences', [os.path.join(root, d)]
                )
            except ImportError:
                continue
            module_name = f'{d}.evidences'
            if module_name in sys.modules:
                continue
            imp.load_module(module_name, *mod_data)


def substitute_config(path_tmpl):
    """
    Substitue the config values on the given path template.

    :param path_tmpl: a string template of a path
    """
    return path_tmpl.format(**(get_config().raw_config))
