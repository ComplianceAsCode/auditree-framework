# Copyright (c) 2023 EnterpriseDB. All rights reserved.
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

"""GitHub demo checks."""

import json

from compliance.check import ComplianceCheck
from compliance.evidence import with_raw_evidences

from demo_examples.evidence import utils

from parameterized import parameterized


class GitHubAPIVersionsCheck(ComplianceCheck):
    """Perform analysis on GitHub supported versions API response evidence."""

    @property
    def title(self):
        """
        Return the title of the checks.

        :returns: the title of the checks
        """
        return "GitHub API Versions"

    @with_raw_evidences("github/api_versions.json")
    def test_supported_versions(self, evidence):
        """
        Check whether there are any supported versions.

        Always warn about something, for demo purposes.
        """
        version_list = json.loads(evidence.content)
        versions_str = ", ".join(version_list)
        if not version_list:
            self.add_failures(
                "Supported GitHub API Versions Violation",
                "No API versions were indicated as supported by GitHub.",
            )
        elif len(version_list) == 1:
            self.add_warnings(
                "Supported GitHub API Versions Warning",
                "There is only one supported version. "
                f"Get with the program: {versions_str}",
            )
        elif len(version_list) > 1:
            self.add_warnings(
                "Supported GitHub API Versions Warning",
                "There are more than one supported versions. "
                f"Check the docs for the latest changes: {versions_str}",
            )

    def get_reports(self):
        """
        Provide the check report name.

        :returns: the report(s) generated for this check
        """
        return ["github/api_versions.md"]

    def msg_supported_versions(self):
        """
        Supported GitHub API versions check notifier.

        :returns: notification dictionary.
        """
        return {"subtitle": "Supported GitHub API Versions Violation", "body": None}


class GitHubOrgs(ComplianceCheck):
    """Perform analysis on GitHub some orgs."""

    @property
    def title(self):
        """
        Return the title of the checks.

        :returns: the title of the checks
        """
        return "GitHub Org checks"

    @parameterized.expand(utils.get_gh_orgs)
    def test_members_is_not_empty(self, org):
        """Check whether the GitHub org is not empty."""
        evidence = self.locker.get_evidence(f"raw/github/{org}_members.json")
        members = json.loads(evidence.content)
        if not members:
            self.add_failures(org, "There is nobody!")
        elif len(members) < 5:
            self.add_warnings(org, "There are people in there, but less than 5!")

    def get_reports(self):
        """Return GitHub report name."""
        return ["github/members.md"]
