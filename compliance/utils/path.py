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
import sys
from pathlib import Path

from compliance.config import get_config

FETCH_PREFIX = 'fetch_'
CHECK_PREFIX = 'test_'


def get_toplevel_dirpath(path):
    """
    Provide the top level directory for the given path.

    The top level directory contains the ``controls.json`` file.
    This function returns ``None`` if a top level path can not be found.

    :param path: absolute or relative path to a file or directory.

    :returns: the absolute path to the top level directory.
    """
    if path is None:
        return
    paths = list(Path(path).resolve().parents)
    if Path(path).resolve().is_dir():
        paths = [Path(path).resolve()] + paths
    for path in paths[:-1]:
        if Path(path, 'controls.json').is_file():
            return str(path)


def load_evidences_modules(path):
    """
    Load all evidences modules found within the ``path`` directory structure.

    This function prevents double loading.

    :param path: absolute path to a top level directory.
    """
    subdirs = [p.parent for p in Path(path).rglob('evidences') if p.is_dir()]
    for subdir in subdirs:
        try:
            mod_data = imp.find_module('evidences', [str(subdir)])
        except ImportError:
            continue
        module_name = f'{subdir.name}.evidences'
        if module_name in sys.modules:
            continue
        imp.load_module(module_name, *mod_data)


def substitute_config(path_tmpl):
    """
    Substitute the config values on the given path template.

    :param path_tmpl: a string template of a path
    """
    return path_tmpl.format(**(get_config().raw_config))
