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
"""Compliance Pagerduty service helper."""

import json
from urllib.parse import urljoin

from compliance.utils.credentials import Config

import requests

PAGERDUTY_API_URL = "https://api.pagerduty.com"
PD_EVENTS_V2_URL = "https://events.pagerduty.com/v2/enqueue"
# 100 is the maximum page size
PAGES_LIMIT = 100


def _init_request(path, params, headers, creds):
    credentials = creds or Config()
    hdrs = {
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Authorization": f'Token token={credentials["pagerduty"].api_key}',
    }
    if headers:
        hdrs.update(headers)
    params = params or {}
    url = urljoin(PAGERDUTY_API_URL, path)
    return url, params, hdrs


def get(path, params=None, headers=None, creds=None):
    """
    Perform a GET operation.

    Returns the pages wrapped as :py:class:`requests.Response` object.
    This uses the PD API v2.

    :param path: API endpoint to call (e.g. 'users')
    :param params: a dictionary with parameters
    :param headers: a dictionary with headers to include
    :param creds: a Config object with PagerDuty credentials
    """
    url, params, hdrs = _init_request(path, params, headers, creds)
    offset = 0
    params.update({"limit": PAGES_LIMIT, "offset": offset})
    more = True
    while more:
        r = requests.get(url, headers=hdrs, params=params)
        yield r
        more = r.json().get("more", False)
        if more:
            offset = offset + PAGES_LIMIT
            params.update({"offset": offset})


def delete(path, params=None, headers=None, creds=None):
    """
    Perform a DELETE operation.

    Returns the result as :py:class:`requests.Response` object.
    This uses the PD API v2.

    :param path: API endpoint to call (e.g. 'users')
    :param params: a dictionary with parameters
    :param headers: a dictionary with headers to include
    :param creds: a Config object with PagerDuty credentials
    """
    url, params, hdrs = _init_request(path, params, headers, creds)
    return requests.delete(url, headers=hdrs, params=params)


def put(path, params=None, headers=None, creds=None):
    """
    Perform a PUT operation.

    Return the result as :py:class:`requests.Response` object.
    This uses the PD API v2.

    :param path: API endpoint to call (e.g. 'users')
    :param params: a dictionary with parameters
    :param headers: a dictionary with headers to include
    :param creds: a Config object with PagerDuty credentials
    """
    url, params, hdrs = _init_request(path, params, headers, creds)
    return requests.put(url, headers=hdrs, params=params)


def post(path, params=None, headers=None, creds=None):
    """
    Perform a POST operation.

    Returns the result as :py:class:`requests.Response` objects.
    This uses the PD API v2.

    :param path: API endpoint to call (e.g. 'users')
    :param params: a dictionary with parameters
    :param headers: a dictionary with headers to include
    :param creds: a Config object with PagerDuty credentials
    """
    url, params, hdrs = _init_request(path, params, headers, creds)
    return requests.post(url, headers=hdrs, params=params)


def send_event(
    action, check, title, source, severity="error", details="", links=None, creds=None
):
    """Send an event to PD using the Events API."""
    credentials = creds or Config()

    msg = {
        "event_action": action,
        "routing_key": credentials["pagerduty"].events_integration_key,
        "dedup_key": check,
        "payload": {
            "summary": title,
            "source": source,
            "severity": severity,
            "custom_details": details,
        },
        "links": links or [],
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(PD_EVENTS_V2_URL, headers=headers, data=json.dumps(msg))
    response.raise_for_status()
    if response.json().get("status") != "success":
        raise RuntimeError("PagerDuty Error: " + response.json())
