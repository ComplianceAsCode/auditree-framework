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
"""Compliance automation compliance tests package."""

from unittest.mock import MagicMock, Mock, PropertyMock

from compliance.check import ComplianceCheck


def build_test_mock(name="one", baseurl="http://mockedrunbooks", fails=0, warns=0):
    """Build a mock of a ComplianceCheck, with minimal attributes set."""
    mock_test = MagicMock()
    if baseurl:
        type(mock_test.test).runbook_url = PropertyMock(
            return_value=f"{baseurl}/path/to/runbook_{name}"
        )
        type(mock_test.test).enabled = PropertyMock(return_value=True)
    else:
        type(mock_test.test).runbook_url = PropertyMock(return_value="")
        type(mock_test.test).enabled = PropertyMock(return_value=False)

    type(mock_test.test).title = PropertyMock(return_value=f"mock check title {name}")

    mock_test.test.failures_count = Mock(return_value=fails)
    mock_test.test.warnings_count = Mock(return_value=warns)

    mock_test.test.__str__.return_value = f"test_{name}"
    mock_test.test.fixed_failure_count = 0
    return mock_test


def build_compliance_check(class_name, title, report, tests=None, fix_return=True):
    """
    Build an actual :py:class:`compliance.check.ComplianceCheck` subclass.

    Class is based on the specific attributes given.

    If multiple tests are provided, then corresponding fix functions
    will be created; otherwise, just a single fix_failures() function
    will be created.

    All fix functions will be set up to call a single function called
    fix_one(), passing the name of the test as the parameter param.

    :param class_name: the name of the class to build
    :param title: the title property of the class
    :param report: the string that the get_reports() function
      should return
    :param tests: list of strings of test functions to add to
      the class. each one will simply assert a true statement
      and return.
    :param fix_return: boolean specifying whether the fix function
      should return True (indicating it fixed the issue) or False
      (indicating it tried but failed)
    """
    tests = tests or []
    fcts = {
        "title": property(lambda self: title),
        "get_reports": lambda self: [report],
        "fix_one": MagicMock(return_value=fix_return),
        "tests": property(lambda self: tests),
    }

    for test in tests:
        fcts[test] = lambda self: self.assertEqual(0, 0)
        fix_fct = "fix_failures"
        if len(tests) > 1:
            fix_fct = test.replace("test_", "fix_")
        fcts[fix_fct] = lambda self, fixer, t=test: (
            fixer.execute_fix(self, self.fix_one, {"param": t})
        )

    cls = type(class_name, (ComplianceCheck,), fcts)
    vars(cls)["fix_one"].__doc__ = "Fixing {param}"

    return cls


def build_compliance_check_obj(*args, **kwargs):
    """
    Build a :py:class:`compliance.check.ComplianceCheck` class.

    Class built using build_compliance_check(), and then create a
    single object from this class and returns it.
    """
    cls = build_compliance_check(*args, **kwargs)
    obj = cls("__doc__")
    return obj
