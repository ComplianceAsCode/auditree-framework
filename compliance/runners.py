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
"""Compliance automation flow management module."""

import inspect
import json
import re
import sys
import time
import unittest
from collections import defaultdict
from importlib import import_module
from pathlib import Path

from compliance.check import ComplianceCheck
from compliance.config import get_config
from compliance.controls import ControlDescriptor
from compliance.fetch import ComplianceFetcher
from compliance.fix import Fixer
from compliance.locker import Locker
from compliance.notify import get_notifiers
from compliance.report import ReportBuilder
from compliance.utils.exceptions import LockerPushError
from compliance.utils.path import (
    CHECK_PREFIX,
    FETCH_PREFIX,
    get_toplevel_dirpath,
    load_evidences_modules,
)


class _BaseRunner(object):
    """Base class for fetcher and check processing."""

    def __init__(self, opts, extra_opts):
        self.opts = opts
        self.extra_opts = extra_opts
        self.load_errors = set()

    def __enter__(self):
        self.init_config()

    def __exit__(self, typ, val, traceback):
        pass

    def init_config(self):
        """Initialize the framework configuration."""
        self._load_compliance_config()
        self._init_dirs()
        ComplianceFetcher.config = self.config
        ComplianceCheck.config = self.config

    def init_locker(self, ttl_tolerance=0):
        """
        Initialize the framework locker.

        :param ttl_tolerance: Evidence TTL tolerance in seconds
        """
        self.locker = self._create_the_locker(ttl_tolerance)
        self.locker.init()
        self.locker.logger_init_msgs()
        for path in self.opts.force:
            self.locker.forced_evidence.append(path)
        ComplianceFetcher.locker = self.locker
        ComplianceCheck.locker = self.locker

    def get_test_candidates(self, suite):
        """
        Provide the test cases from a test suite.

        :param suite: a TestSuite object

        :returns: generator iterable of test cases
        """
        for suite_test in suite:
            if unittest.suite._isnotsuite(suite_test):
                yield suite_test
                continue
            for test in self.get_test_candidates(suite_test):
                yield test

    def _load_compliance_config(self):
        creds_path = Path(self.opts.creds_path).expanduser()
        if not creds_path.is_file():
            raise ValueError(f"{creds_path} file does not exist.")
        self.config = get_config()
        self.config.creds_path = str(creds_path)
        self.config.load(self.opts.compliance_config)

    def _init_dirs(self):
        self.dirs = set()
        for p in [Path(path).resolve() for path in self.extra_opts + ["."]]:
            if p.exists():
                dirpath = get_toplevel_dirpath(p)
                if dirpath is None:
                    continue
                self.dirs.add(dirpath)
        if not self.dirs:
            raise ValueError("Could not find a controls.json file.")
        for d in self.dirs:
            load_evidences_modules(d)

    def _create_the_locker(self, ttl_tolerance):
        dirname = self.config.get("locker.dirname")
        mode = self.opts.evidence

        gitconfig = self.config.get("locker.gitconfig")
        if mode == "local":
            return Locker(
                name=dirname,
                ttl_tolerance=ttl_tolerance,
                gitconfig=gitconfig,
                branch=self.config.get("locker.branch"),
                local_path=self.config.get("locker.local_path"),
            )
        repo_url = self.config.get("locker.repo_url")
        if repo_url is None:
            raise ValueError(f'Evidence mode "{mode}" requires a URL.')
        return Locker(
            name=dirname,
            repo_url=repo_url,
            creds=self.config.creds,
            do_push=True if mode == "full-remote" else False,
            ttl_tolerance=ttl_tolerance,
            gitconfig=gitconfig,
            branch=self.config.get("locker.branch"),
            local_path=self.config.get("locker.local_path"),
        )


class FetchMode(_BaseRunner):
    """The fetcher process flow."""

    def __enter__(self):
        """Initialize fetcher mode processing."""
        super(FetchMode, self).__enter__()
        self.init_locker(self.config.get("locker.ttl_tolerance", 0))
        return self

    def __exit__(self, typ, val, traceback):
        """Handle post fetcher test execution processing."""
        super(FetchMode, self).__exit__(typ, val, traceback)
        # make sure that all added evidence are committed
        self.locker.checkin()
        # Only push if fetchers are run separately from checks,
        # otherwise push occurs after check processing is complete.
        if not self.opts.check:
            try:
                self.locker.push()
            except LockerPushError as lpe:
                self.locker.logger.error(str(lpe))

    def get_fetchers(self):
        """Provide all compliance framework fetcher classes."""
        fetchers = set()
        for loc in self.dirs:
            tl = unittest.TestLoader()
            tl.testMethodPrefix = FETCH_PREFIX
            candidates = self.get_test_candidates(
                tl.discover(loc, f"{FETCH_PREFIX}*.py")
            )
            for candidate in candidates:
                if issubclass(candidate.__class__, ComplianceFetcher):
                    fetchers.add(candidate.__class__)
            for load_err in tl.errors:
                try:
                    locate = re.search(
                        "^Failed to import test module: (.+?)\n.*?", load_err
                    )
                    if locate.group(1).split(".")[-1].startswith(FETCH_PREFIX):
                        self.load_errors.add(load_err)
                except AttributeError:
                    pass
        if not (self.opts.include or self.opts.exclude):
            return fetchers
        include = {f"{f.__module__}.{f.__name__}" for f in fetchers}
        if self.opts.include:
            include = set(json.loads(Path(self.opts.include).read_text()))
            for test in include:
                if test in fetchers:
                    continue
                test_name, test_class = test.rsplit(".", 1)
                try:
                    # Attempt to import missing fetchers.
                    fetchers.add(getattr(import_module(test_name), test_class))
                    import_module(".".join([test.split(".")[0], "evidences"]))
                except (AttributeError, ModuleNotFoundError):
                    continue
        exclude = set()
        if self.opts.exclude:
            exclude = set(json.loads(Path(self.opts.exclude).read_text()))
        include -= exclude
        return filter(lambda f: f"{f.__module__}.{f.__name__}" in include, fetchers)

    def run_fetchers(self, reruns=None):
        """
        Execute fetchers.

        :param reruns: A list of fetchers in dot notation to rerun

        :returns: Success (True) if no errors other than dependency unavailable
        """
        loader = unittest.TestLoader()
        loader.testMethodPrefix = FETCH_PREFIX
        fetchers = unittest.TestSuite()
        if reruns is None:
            fetcher_overrides = [
                fo for fo in self.extra_opts if not Path(fo).resolve().exists()
            ]
            if fetcher_overrides:
                fetchers.addTests(loader.loadTestsFromNames(fetcher_overrides))
            else:
                for fetcher in self.get_fetchers():
                    fetchers.addTests(loader.loadTestsFromTestCase(fetcher))
        else:
            self.config.dependency_rerun = True
            self.locker.reset_depenency_rerun()
            fetchers.addTests(loader.loadTestsFromNames(reruns))
        runner = unittest.TextTestRunner(
            verbosity=self.opts.verbose, resultclass=ComplianceBaseResult
        )
        return all(
            (
                "DependencyUnavailableError" in tb.split("Traceback")[-1]
                for (_, tb) in runner.run(fetchers).errors
            )
        )


class CheckMode(_BaseRunner):
    """The check process flow."""

    def __init__(self, opts, extra_opts):
        """
        Construct and initialize the check mode context manager.

        :param opts: arguments provided from the command line.
        :param extra_opts: additional arguments provided from the command line.
        """
        super(CheckMode, self).__init__(opts, extra_opts)
        self.accreds = [a.strip() for a in opts.check.split(",")]
        # Backward compatibility to support ghe_issues option
        self.notifiers = [
            n.strip().replace("ghe_issues", "gh_issues") for n in opts.notify.split(",")
        ]
        self.push_error = False

    def __enter__(self):
        """Initialize check mode processing."""
        super(CheckMode, self).__enter__()
        self.init_locker()
        return self

    def __exit__(self, typ, val, traceback):
        """Handle post check test execution processing."""
        super(CheckMode, self).__exit__(typ, val, traceback)
        try:
            self.build_reports()
            # When in full-remote mode, fixers only run if push was successful
            self.fix_failures()
        except LockerPushError as lpe:
            self.locker.logger.error(str(lpe))
            self.push_error = True
        self.run_notifiers()

    def init_config(self):
        """Initialize the framework configuration for check execution."""
        super(CheckMode, self).init_config()
        self.results = None
        self.controls = ControlDescriptor(self.dirs)

    def get_checks(self):
        """Provide the appropriate compliance framework check classes."""
        checks = set()
        tests_found = set()
        for loc in self.dirs:
            tl = unittest.TestLoader()
            tl.testMethodPrefix = CHECK_PREFIX
            candidates = self.get_test_candidates(
                tl.discover(loc, f"{CHECK_PREFIX}*.py")
            )
            for test in [c.__class__ for c in candidates]:
                path = f"{test.__module__}.{test.__name__}"
                tests_found.add(path)
                in_accred_grouping = self.controls.is_test_included(path, self.accreds)
                if issubclass(test, ComplianceCheck) and in_accred_grouping:
                    test.tests = [
                        method
                        for method in dir(test)
                        if (
                            method.startswith(CHECK_PREFIX)
                            and (
                                inspect.ismethod(getattr(test, method))
                                or inspect.isfunction(getattr(test, method))
                            )
                        )
                    ]
                    checks.add(test)
            for load_err in tl.errors:
                try:
                    locate = re.search(
                        "^Failed to import test module: (.+?)\n.*?", load_err
                    )
                    for accred in self.accreds:
                        for check in self.controls.accred_checks[accred]:
                            if check.startswith(locate.group(1)):
                                self.load_errors.add(
                                    f"Unable to load {check}\n\n{load_err}"
                                )
                                tests_found.add(check)
                except AttributeError:
                    pass
        expected_checks = set()
        for accred, checks_in_accred in self.controls.accred_checks.items():
            if accred in self.accreds:
                expected_checks.update(checks_in_accred)
        for check_not_found in expected_checks - tests_found:
            self.load_errors.add(
                (
                    f"Unable to load {check_not_found}\n\n"
                    f"The check {check_not_found} was not found.  "
                    "Please validate that the path provided is correct."
                )
            )
        return checks

    def run_checks(self):
        """
        Execute checks.

        :returns: Success (True) if no errors encountered
        """
        loader = unittest.TestLoader()
        loader.testMethodPrefix = CHECK_PREFIX
        checks = unittest.TestSuite()
        for check in self.get_checks():
            checks.addTests(loader.loadTestsFromTestCase(check))
        runner = unittest.TextTestRunner(
            verbosity=self.opts.verbose, resultclass=ComplianceCheckResult
        )
        check_run = runner.run(checks)
        self.results = check_run.results
        return False if check_run.errors else True

    def fix_failures(self):
        """Fix failures if fixer methods are included in checks."""
        if self.opts.fix != "off":
            fixer = Fixer(self.results, dry_run=(self.opts.fix == "dry-run"))
            fixer.fix()

    def build_reports(self):
        """Generate reports based on check results."""
        builder = ReportBuilder(self.locker, self.results, self.controls)
        builder.build()

    def run_notifiers(self):
        """Execute all requested notifiers."""
        sys.stdout.flush()
        sys.stderr.flush()
        notifiers = get_notifiers()
        for notifier_name in self.notifiers:
            notifier_args = [self.results, self.controls]
            if notifier_name == "locker":
                notifier_args.append(self.locker)
            notifier = notifiers[notifier_name](
                *notifier_args, push_error=self.push_error
            )
            notifier.notify()


class ComplianceBaseResult(unittest.TextTestResult):
    """Base Compliance result class."""

    def startTest(self, test):  # noqa: N802
        """Start test timer for each test."""
        super(ComplianceBaseResult, self).startTest(test)
        if self.showAll:
            self.start_time = time.perf_counter()

    def stopTest(self, test):  # noqa: N802
        """Report on execution time at the end of each test."""
        super(ComplianceBaseResult, self).stopTest(test)
        if self.showAll:
            time_taken = time.perf_counter() - self.start_time
            self.stream.write(f"{self.getDescription(test)} - ran in: ")
            self.stream.writeln(f"{time_taken:.3f}s")
            self.stream.flush()


class ComplianceCheckResult(ComplianceBaseResult):
    """Compliance check result class."""

    def __init__(self, *args, **kwargs):
        """Construct and initialize the compliance check result."""
        super(ComplianceCheckResult, self).__init__(*args, **kwargs)
        self.results = defaultdict(dict)

    def addSuccess(self, test):  # noqa: N802
        """
        Add test successes and warnings to check results.

        :param test: a ``unittest.TestCase`` object.
        """
        super(ComplianceCheckResult, self).addSuccess(test)
        self.record(test, "pass" if test.warnings_count() == 0 else "warn")

    def addError(self, test, err):  # noqa: N802
        """
        Add test errors to check results.

        :param test: a ``unittest.TestCase`` object.
        :param err: a tuple of the form returned by sys.exc_info()
        """
        super(ComplianceCheckResult, self).addError(test, err)
        self.record(test, "error")

    def addFailure(self, test, err):  # noqa: N802
        """
        Add test failures to check results.

        :param test: a ``unittest.TestCase`` object.
        :param err: a tuple of the form returned by sys.exc_info()
        """
        super(ComplianceCheckResult, self).addFailure(test, err)
        self.record(test, "fail")

    def record(self, test, status):
        """
        Populate the results as expected by downstream reports and notifiers.

        :param test: a ``unittest.TestCase`` object.
        :param status: a string status (`pass`, `warn`, `fail`, or `error`)
        """
        self.results[test.id()] = {
            "status": status,
            "timestamp": time.time(),
            "test": ComplianceTestWrapper(test),
        }


class ComplianceTestWrapper(object):
    """
    TestCase wrapper class.

    Wraps the TestCase test object as an attribute to ensure backwards
    compatibility with checks, reporting, and notifiers.
    """

    def __init__(self, test):
        """Construct and initialize the test case wrapper object."""
        self.test = test
