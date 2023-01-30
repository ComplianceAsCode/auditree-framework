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
"""Compliance credentials configuration."""

import logging
from collections import OrderedDict, namedtuple
from configparser import RawConfigParser
from os import environ
from pathlib import Path

# used to differentiate a user passing None vs
# not passing a value for an optional argument
_sentinel = object()

logger = logging.getLogger("compliance.utils.credentials")


class Config:
    """Handle credentials configuration."""

    def __init__(self, cfg_file="~/.credentials"):
        """
        Create an instance of a dictionary-like configuration object.

        :param cfg_file: The path to the RawConfigParser compatible config file
        """
        self._cfg = RawConfigParser()
        self._cfg.read(str(Path(cfg_file).expanduser()))
        self._cfg_file = cfg_file

    def __getitem__(self, section):
        """
        Get the named tuple representing the configuration held at `section`.

        Build a named tuple representing the configuration at `section`. If a
        config file does not have an option for the section ignore it.
        Resulting in an AttributeError if accessed later in the code.

        :param section: the section to retrieve
        """

        def _getattr_wrapper(t, attr):
            """
            Replace the standard __getattr__ functionality.

            In the case when a section and/or attribute is not set in the
            config file, the error shown will be more helpful.
            """
            try:
                return t.__getattribute__(attr)
            except AttributeError as exc:
                exc.args = (
                    (
                        f'Unable to locate attribute "{attr}" '
                        f'in section "{type(t).__name__}" '
                        f'at config file "{self._cfg_file}"'
                    ),
                )
                raise exc

        env_vars = [k for k in environ.keys() if k.startswith(f"{section.upper()}_")]
        env_keys = [k.split(section.upper())[1].lstrip("_").lower() for k in env_vars]
        env_values = [environ[e] for e in env_vars]
        if env_vars:
            logger.debug(f'Loading credentials from ENV vars: {", ".join(env_vars)}')
        params = []
        if self._cfg.has_section(section):
            params = self._cfg.options(section)
        values = [self._cfg.get(section, x) for x in params]

        d = OrderedDict(zip(params, values))

        if env_vars:
            d.update(zip(env_keys, env_values))
        t = namedtuple(section, " ".join(list(d.keys())))
        t.__getattr__ = _getattr_wrapper
        return t(*list(d.values()))

    def get(self, section, key=None, account=None, default=_sentinel):
        """
        Retrieve sections and keys by account.

        :param section: the section from which to retrieve keys.
        :parm key: the key in the section whose value you want to retrieve. if
          not specified, returns the whole section as a dictionary.
        :param account: if provided, fetches the value for the specific account.
          assumes the account is prefixed to the key and separated by _.
        :param default: if provided, returns this value if a value cannot be
          found; otherwise raises an exception.
        """
        if key is None:
            return self[section]
        if account:
            key = "_".join([account, key])
        if default == _sentinel:
            return getattr(self[section], key)
        else:
            return getattr(self[section], key, default)
