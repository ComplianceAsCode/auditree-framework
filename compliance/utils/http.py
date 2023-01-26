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
"""Compliance HTTP helpers."""

import requests


class BaseSession(requests.Session):
    """Subclass of requests.Session to support a base URL."""

    def __init__(self, baseurl):
        """
        Set the baseurl for the session.

        All requests using this session will be run against this URL.
        """
        super(BaseSession, self).__init__()
        self.baseurl = baseurl.strip("/")

    def prepare_request(self, request):
        """Prefix with self.baseurl if request.url does not include it."""
        if not request.url.startswith(self.baseurl):
            # the behavior of urljoin isn't what we want here
            request.url = f'{self.baseurl}/{request.url.lstrip("/")}'
        return super(BaseSession, self).prepare_request(request)
