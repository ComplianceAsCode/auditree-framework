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
"""Compliance configuration automation module."""

import inspect
import json
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path

from compliance.utils.credentials import Config


class ComplianceConfig(object):
    """
    The configuration for a compliance run.

    Credentials and a cache of known evidences are included.
    """

    DEFAULTS = {
        "locker": {
            "dirname": "compliance",
            "repo_url": "https://github.com/YOUR_ORG/YOUR_PROJECT",
        },
        "runbooks": {"enabled": False, "base_url": "https://example.com/runbooks"},
        "notify": {
            # Slack channel to use for an accreditation
            # E.g. {"mycompany.soc2": ["#compliance"]}
            "slack": {},
            # GH repo to use for an accreditation
            # E.g. {"mycompany.soc2": {"repo": ["my-org/accr1-repo"]}}
            "gh_issues": {},
            # GHE repo to use for an accreditation
            # Deprecated (use gh_issues), included for backward compatibility.
            # E.g. {"mycompany.soc2": {"repo": ["my-org/accr1-repo"]}}
            "ghe_issues": {},
            # Pagerduty service id to use for an accreditation
            # E.g. {"mycompany.soc2": "ABCDEFG"}
            "pagerduty": {},
            # Security Advisor FindingsAPI endpoint to use for an accreditation
            # E.g. {"mycompany.soc2": "https://my.findings.api/findings"}
            "findings": {},
        },
        "org": {"name": "YOUR_ORG", "settings": {}},
    }

    def __init__(self):
        """Construct and initialize the configuration object."""
        self._config = {}
        self._creds = None
        self._evidence_cache = OrderedDict()
        self._org = None
        self.creds_path = None
        self.dependency_rerun = False

    @property
    def creds(self):
        """Credentials used for locker management and running fetchers."""
        if self.creds_path is None:
            raise ValueError("Path to credentials file not provided")

        if self._creds is None:
            self._creds = Config(self.creds_path)
        return self._creds

    @property
    def evidences(self):
        """All evidence objects currently in the evidence cache."""
        return self._evidence_cache.values()

    @property
    def raw_config(self):
        """Raw configuration settings as a dictionary."""
        return self._config

    def load(self, config_file=None):
        """
        Load configuration from a JSON file.

        :param config_file: the path to the JSON config file.
          If ``None``, the ``DEFAULT`` configuration is used.
        """
        if config_file is None:
            self._config = self.DEFAULTS.copy()
            return
        try:
            self._config = json.loads(Path(config_file).read_text())
        except ValueError as err:
            err.args += (config_file,)
            raise

    def get(self, config_path, default=None):
        """
        Provide the configuration value for the supplied ``config_path``.

        Returns the default if ``config_path`` cannot be retrieved.

        :param config_path: dot notation path with the following format
          ``'key[.subkey]``. For instance, ``locker.dirname``.
        """
        chunks = config_path.split(".")
        value = self._config
        for c in chunks:
            if value is None:
                break
            value = value.get(c)
        if value is None:
            value = self.DEFAULTS
            for c in chunks:
                if value is None:
                    break
                value = value.get(c)
        return deepcopy(value) if value is not None else deepcopy(default)

    def get_evidence(self, evidence_path):
        """
        Provide an evidence object from the evidence cache.

        :param path: the path to the evidence within the Locker.
          For example, ``raw/source1/evidence.json``
        """
        return self._evidence_cache.get(evidence_path)

    def add_evidences(self, evidence_list):
        """
        Add a list of evidence objects to the evidence cache.

        :param evidence_list: a list of evidence objects.
        """
        for e in evidence_list:
            if not self.dependency_rerun and e.path in self._evidence_cache.keys():
                raise ValueError(f"Evidence {e.path} duplicated")
            self._evidence_cache[e.path] = e

    def get_template_dir(self, test_obj=None):
        """
        Provide absolute path to the template directory for the test object.

        The associated path will be the first directory found named
        ``templates`` in the test object absolute path traversed in reverse.
        If ``test_obj`` is ``None``, then current directory ``'.'`` is
        assumed as initial path.

        :param test_obj: a :class:`compliance.ComplianceTest` object from
          where the template directory search will start from.
        """
        paths = [Path().resolve()] + list(Path().resolve().parents)
        if test_obj is not None:
            paths = list(Path(inspect.getfile(test_obj.__class__)).parents)
        for path in paths[:-1]:
            templates = Path(path, "templates")
            if templates.is_dir():
                return str(templates)


__config = None


def get_config():
    """Provide the global configuration object."""
    global __config
    if __config is None:
        __config = ComplianceConfig()
    return __config
