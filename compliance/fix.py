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
"""Compliance fixer automation module."""

import sys

from compliance.config import get_config
from compliance.utils.test import parse_test_id


class Fixer(object):
    """This class attempts to resolve check failures."""

    def __init__(self, results, dry_run=True, out=sys.stdout):
        """
        Construct and initialize the fixer object.

        :param results: dictionary of check results.
        :param dry_run: dictate whether to inform or perform actions to fix.
        :param out: where to write the output for dry-run messages.
        """
        self._results = results
        self._dry_run = dry_run
        self._out = out
        self._creds = get_config().creds

    def fix(self):
        """
        Perform all fix routines found in executed checks.

        Iterate through all compliance checks and looks for `fix_*` methods
        with corresponding `test_*` methods. These are executed, and results
        are recorded if fixes are made.

        Note: Instead of individual `fix_*` methods, you can instead define
        a single `fix_failures` method which handles all fixes for the class.
        """
        if not self._results:
            return

        for test_id, test_desc in self._results.items():
            if test_desc["status"] != "fail":
                continue

            test_obj = test_desc["test"].test
            method_name = parse_test_id(test_id)["method"]
            candidate = method_name.replace("test_", "fix_")

            if len(test_obj.tests) > 1 and hasattr(test_obj, candidate):
                getattr(test_obj, candidate)(self)
            elif hasattr(test_obj, "fix_failures"):
                test_obj.fix_failures(self)

    def execute_fix(self, test_obj, fct, args=None):
        """
        Execute the fix routine for a given check test object.

        This method gets called by fix_* methods in checks.
        It gets passed a function (method) that must be called in order
        to fix one specific issue.  The method's fix will either get
        executed, or if in dry-run mode, will print out the method's
        docstring, injecting any arguments if needed.  The check's
        fixed_failure_count is incremented if the fix was successful.

        :param test_obj: instance of subclass of
          :py:class:`compliance.utils.check.ComplianceCheck` on which
          to execute the fix
        :param fct: a callback function that will actually perform
          the fix. this function will be passed a reference to this
          fixer, along with a reference to a
          compliance.utils.credentials.Config object. this
          callback will also need to have a docstring, which is
          what will be displayed in dry-run mode. the docstring
          will get formatted with the arguments passed to the fix
          function.
        :param args: dictionary of named arguments to pass to the
          fix function fct.
        """
        args = args or {}
        if self._dry_run:
            self._out.write(f"DRY-RUN: {fct.__doc__.format(**args)}\n")
        else:
            success = fct(**dict(list(args.items()) + [("creds", self._creds)]))
            if success:
                test_obj.fixed_failure_count += 1
