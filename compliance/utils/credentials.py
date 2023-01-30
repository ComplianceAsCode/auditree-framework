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
import os
import shlex
import subprocess  # nosec B404
from collections import OrderedDict, namedtuple
from configparser import RawConfigParser
from os import environ
from pathlib import Path

# used to differentiate a user passing None vs
# not passing a value for an optional argument
_sentinel = object()

logger = logging.getLogger("compliance.utils.credentials")


class OnePasswordBackend:
    def __init__(self, **kwargs):
        self._url = kwargs.get("url")
        self._vault = kwargs.get("vault", "auditree")

    def get_section(self, section):
        cmd = f"op item get --vault {self._vault} --format json {section}"
        subprocess.run(  # nosec B603
            shlex.split(cmd),
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def attribute_error_msg(self, section, attr):
        return (
            f'Unable to locate field "{attr}" '
            f'in secure note "{section}" '
            f'at 1Password vault "{self._vault}"'
        )


class ConfigParserBackend:
    def __init__(self, **kwargs):
        self._cfg = RawConfigParser()
        self._cfg_file = kwargs.get("cfg_file")
        self._cfg.read(str(Path(self._cfg_file).expanduser()))

    def get_section(self, section):
        params = []
        values = []
        if self._cfg.has_section(section):
            params = self._cfg.options(section)
            values = [self._cfg.get(section, x) for x in self._cfg.options(section)]
        return OrderedDict(zip(params, values))

    def attribute_error_msg(self, section, attr):
        return (
            f'Unable to locate attribute "{attr}" '
            f'in section "{section}" '
            f'at config file "{self._cfg_file}"'
        )


class Config:
    """Handle credentials configuration."""

    BACKENDS = {"1password": OnePasswordBackend, "configparser": ConfigParserBackend}

    def __init__(self, cfg_file="~/.credentials", backend_cfg=None):
        """
        Create an instance of a dictionary-like configuration object.

        :param cfg_file: The path to a config file for building a ConfigParserBackend.
        :param backend_cfg: A dictionary with the backend config
        """

        if backend_cfg is None:
            backend_cfg = {"name": "configparser", "cfg_file": cfg_file}
        self._init_backend(backend_cfg)

    def _init_backend(self, backend_cfg):
        """
        Create an instance of a dictionary-like configuration object.

        :param cfg_file: The path to the RawConfigParser compatible config file
        """
        name = backend_cfg.get("name")
        if backend_cfg.get("name") not in Config.BACKENDS:
            raise ValueError(f"Invalid credentials backend name: {name}")
        self._backend = Config.BACKENDS[name](**backend_cfg)

    @classmethod
    def from_auditree_config(cls, at_cfg):
        return cls(backend_cfg=at_cfg.get("creds.backend"))

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
                exc.args = (self._backend.attribute_error_msg(type(t).__name__, attr),)
                raise exc

        env_vars = [k for k in environ.keys() if k.startswith(f"{section.upper()}_")]
        env_keys = [k.split(section.upper())[1].lstrip("_").lower() for k in env_vars]
        env_values = [environ[e] for e in env_vars]
        if env_vars:
            logger.debug(f'Loading credentials from ENV vars: {", ".join(env_vars)}')

        d = self._backend.get_section(section)

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
