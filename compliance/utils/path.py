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

import importlib
import sys
from pathlib import Path, PurePath

from compliance.config import get_config

FETCH_PREFIX = "fetch_"
CHECK_PREFIX = "test_"


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
        if Path(path, "controls.json").is_file():
            return str(path)


def get_module_path(path):
    """
    Provide the full module dot notation path based on the file path provided.

    :param path: absolute or relative path to a file or directory.

    :returns: the module path in dot notation.
    """
    if path is None:
        return
    for parent in PurePath(path).parents:
        if parent.name == "site-packages":
            return _path_to_dot(str(PurePath(path).relative_to(parent)))
    return _path_to_dot(str(PurePath(path).relative_to(get_toplevel_dirpath(path))))


def load_evidences_modules(path):
    """
    Load all evidences modules found within the ``path`` directory structure.

    :param path: absolute path to a top level directory.
    """
    for ev_mod in [p for p in Path(path).rglob("evidences") if p.is_dir()]:
        module_name = get_module_path(str(ev_mod))
        spec = None
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, str(Path(ev_mod, "__init__.py"))
            )
        except ImportError:
            continue
        if spec is None or module_name in sys.modules:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)


def substitute_config(path_tmpl):
    """
    Substitute the config values on the given path template.

    :param path_tmpl: a string template of a path
    """
    return path_tmpl.format(**(get_config().raw_config))


def _path_to_dot(path):
    return path.rstrip(".py").replace("/", ".").replace("\\", ".")
