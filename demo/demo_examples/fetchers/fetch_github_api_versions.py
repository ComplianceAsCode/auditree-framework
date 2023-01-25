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
import json

from compliance.evidence import store_raw_evidence
from compliance.fetch import ComplianceFetcher

class GitHubAPIVersionsFetcher(ComplianceFetcher):
    """Fetch the current supported GitHub API versions."""

    @store_raw_evidence('github/api_versions.json')
    def fetch_api_versions(self):
        """Fetch the current supported GitHub API versions."""
        # This is where you might e.g. fetch your evidence
        # from a remote API
        session = self.session('https://api.github.com/')
        versions = session.get(
            'versions',
            headers={"Accept": "application/json"})
        versions.raise_for_status()
        return versions.text
