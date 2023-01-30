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

"""Evidence module."""

from compliance.config import get_config
from compliance.evidence import DAY, RawEvidence, ReportEvidence

get_config().add_evidences(
    [
        RawEvidence(
            "api_versions.json", "github", DAY, "Supported GitHub API versions"
        ),
        RawEvidence(
            "auditree_logo.png",
            "images",
            DAY,
            "The Auditree logo image",
            binary_content=True,
        ),
        ReportEvidence(
            "api_versions.md", "github", DAY, "Supported GitHub versions report."
        ),
        ReportEvidence("image_check.md", "images", DAY, "Image Check Analysis report."),
    ]
)
