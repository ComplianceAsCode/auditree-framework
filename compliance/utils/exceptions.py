# Copyright (c) 2021, 2022 IBM Corp. All rights reserved.
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
"""Compliance automation custom exceptions module."""


class StaleEvidenceError(Exception):
    """Stale evidence exception class."""

    pass


class EvidenceNotFoundError(ValueError):
    """Missing evidence exception class."""

    pass


class HistoricalEvidenceNotFoundError(ValueError):
    """Missing historical evidence exception class."""

    pass


class DependencyUnavailableError(ValueError):
    """Missing dependent evidence exception class."""

    pass


class DependencyFetcherNotFoundError(ValueError):
    """Dependency fetcher not found exception class."""

    pass


class UnverifiedEvidenceError(Exception):
    """Unverified evidence exception class."""

    pass


class LockerPushError(Exception):
    """Locker push exception class."""

    def __init__(self, push_info=None):
        """
        Construct the locker push exception.

        :param push_info: a GitPython PushInfo object containing Git remote
          push information
        """
        self.push_info = push_info

    def __str__(self):
        """Display the error as a string."""
        msg = "Push to remote locker failed.\n"
        if self.push_info:
            msg += (
                f"       Summary: {self.push_info.summary}"
                f"       Error Flags: {self.push_info.flags}"
            )
        return msg
