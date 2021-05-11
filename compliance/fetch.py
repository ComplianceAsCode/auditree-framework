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
"""Compliance fetcher automation module."""

import shutil
import tempfile
import unittest
from pathlib import Path

from compliance.config import get_config
from compliance.utils.http import BaseSession

import requests


class ComplianceFetcher(unittest.TestCase):
    """Compliance fetcher automation TestCase class."""

    @classmethod
    def tearDownClass(cls):
        """Perform clean up."""
        if hasattr(cls, '_session'):
            cls._session.close()

    @classmethod
    def session(cls, url=None, creds=None, **headers):
        """
        Provide a requests session object with User-Agent header.

        :param url: optional base URL for the session requests to use.  A url
          argument triggers a new session object to be created whereas no url
          argument will return the current session object if one exists.
        :param creds: optional authentication credentials.
        :param headers: optional kwargs to add to session headers.

        :returns: a requests Session object.
        """
        if url is not None and hasattr(cls, '_session'):
            cls._session.close()
            delattr(cls, '_session')
        if not hasattr(cls, '_session'):
            if url:
                cls._session = BaseSession(url)
            else:
                cls._session = requests.Session()
            if creds:
                cls._session.auth = creds
            cls._session.headers.update(headers)
            org = cls.config.raw_config.get('org', {}).get('name', '')
            ua = f'{org.lower().replace(" ", "-")}-compliance-checks'
            cls._session.headers.update({'User-Agent': ua})
        return cls._session

    def __init__(self, *args, **kwargs):
        """Construct and initialize the fetcher test object."""
        super(ComplianceFetcher, self).__init__(*args, **kwargs)
        if hasattr(ComplianceFetcher, 'config'):
            self.config = ComplianceFetcher.config
        else:
            self.config = get_config()

    def fetchURL(self, url, params=None, creds=None):  # noqa: N802
        """
        Retrieve remote content through an HTTP GET request.

        Helper/Convenience method.

        :param url: the URL of the file.
        :param params: optional parameters to include in the GET request.
        :param creds: optional tuple with (user, password) to be used.

        :returns: the remote content.
        """
        org = self.config.raw_config.get('org', {}).get('name', '')
        ua = f'{org.lower().replace(" ", "-")}-compliance-checks'
        response = requests.get(
            url, params=params, auth=creds, headers={'User-Agent': ua}
        )
        response.raise_for_status()
        return response.content

    def fetchCloudantDoc(self, db_url, params=None):  # noqa: N802
        """
        Retrieve a Cloudant document.

        Helper/Convenience method.

        :param db_url: the URL to the Cloudant doc to retrieve.
        :param params: optional parameters to include in the GET request.

        :returns: the Cloudant document content.
        """
        creds = self.config.creds
        return self.fetchURL(
            db_url,
            params=params,
            creds=(creds['cloudant'].user, creds['cloudant'].password)
        )


def fetch(url, name):
    """
    Write content retrieved from provided url to a file.

    :param url: the URL to GET content from.
    :param name: the name of the file to write to in the TMPDIR.

    :returns: the path to the file.
    """
    r = requests.get(url)
    r.raise_for_status()
    path = Path(tempfile.gettempdir(), name)
    with path.open('wb') as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)
    return path
