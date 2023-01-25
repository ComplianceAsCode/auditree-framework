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

"""Demo fetchers for GitHub."""

import json

from compliance.evidence import DAY, RawEvidence, store_raw_evidence
from compliance.fetch import ComplianceFetcher

from demo_examples.evidence import utils

from parameterized import parameterized


class GitHubFetcher(ComplianceFetcher):
    """Fetch the current supported GitHub API versions."""

    @classmethod
    def setUpClass(cls):
        """Initialise the fetcher class with common functionality."""
        cls.client = cls.session(
            'https://api.github.com/', **{'Accept': 'application/json'}
        )

    @store_raw_evidence('github/api_versions.json')
    def fetch_api_versions(self):
        """Fetch the current supported GitHub API versions."""
        # This is where you might e.g. fetch your evidence
        # from a remote API
        versions = self.client.get('versions')
        versions.raise_for_status()
        return versions.text

    @parameterized.expand(utils.get_gh_orgs)
    def fetch_github_members(self, org):
        """Fetch GitHub members from the organization."""
        # We don't use the helper decorator in this case, so we have to manage
        # the envidence life-cycle: creation, fetch and store in the locker.
        evidence = RawEvidence(
            f'{org}_members.json', 'github', DAY, f'GH members of org {org}'
        )

        if self.locker.validate(evidence):
            return
        resp = self.client.get(f'/orgs/{org}/members', params={'page': 1})
        resp.raise_for_status()
        evidence.set_content(json.dumps(resp.json(), indent=2))
        self.locker.add_evidence(evidence)
