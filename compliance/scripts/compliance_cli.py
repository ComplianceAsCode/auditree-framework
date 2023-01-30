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
"""Compliance automation command line interface."""

from compliance import __version__
from compliance.notify import get_notifiers
from compliance.runners import CheckMode, FetchMode

from ilcli import Command


class ComplianceCLI(Command):
    """The Compliance Framework CLI."""

    name = "compliance"

    def _init_arguments(self):
        self.add_argument(
            "-V",
            "--version",
            help="Displays the auditree framework version.",
            action="version",
            version=f"Auditree Framework version v{__version__}",
        )
        self.add_argument(
            "-v",
            "--verbose",
            help="Displays verbose output.",
            action="store_const",
            const=2,
            default=1,
        )
        self.add_argument(
            "--fetch",
            help="Enables the fetch process.",
            action="store_true",
            default=False,
        )
        self.add_argument(
            "--check",
            help=(
                "Enables the check process.  "
                "Check groupings can be a comma separated list without spaces."
            ),
            metavar="chk.grp1,chk.grp2,...",
            nargs="?",
            const="",
        )
        self.add_argument(
            "--evidence",
            help=("Defines the evidence storage mode.  Defaults to %(default)s."),
            choices=["local", "no-push", "full-remote"],
            default="no-push",
        )
        self.add_argument(
            "--fix",
            help="Attempts to fix check failures.  Defaults to %(default)s.",
            choices=["off", "on", "dry-run"],
            default="off",
        )
        self.add_argument(
            "-C",
            "--compliance-config",
            help="Specifies the path/name of the compliance config JSON file.",
            metavar="auditree.json",
            default=None,
        )
        self.add_argument(
            "--creds-path",
            help=(
                "Specifies the path/name of the credentials ini file.  "
                "Defaults to %(default)s."
            ),
            metavar="/path/to/creds.ini",
            default="~/.credentials",
        )
        notify_options = [k for k in get_notifiers().keys() if k != "stdout"]
        self.add_argument(
            "--notify",
            help=(
                "Specifies a list of notifiers for sending notifications.  "
                "Valid values (can be a comma separated list - no spaces): "
                f'{", ".join(notify_options)}.  NOTE: In addition to those '
                "specified, the %(default)s notifier will always execute."
            ),
            metavar="[slack,gh_issues,...]",
            default="stdout",
        )
        self.add_argument(
            "--force",
            help="Forces an evidence to be fetched, ignoring TTL.",
            metavar="raw/category/evidence.ext",
            action="append",
            default=[],
        )
        self.add_argument(
            "--include",
            help="Specifies the path/name of the fetcher include JSON file.",
            metavar="fetchers.json",
            default=None,
        )
        self.add_argument(
            "--exclude",
            help="Specifies the path/name of the fetcher exclude JSON file.",
            metavar="fetchers.json",
            default=None,
        )

    def _validate_arguments(self, args):
        if "stdout" not in args.notify:
            args.notify += ",stdout"
        if args.check == "":
            self.parser.error("--check option requires accreditation grouping(s).")
        if not args.fetch and not args.check:
            self.parser.error("--fetch or --check option is expected.")
        if not args.fetch and (args.include or args.exclude):
            self.parser.error("--include/--exclude options only valid with --fetch.")
        if not args.check and args.fix != "off":
            self.parser.error("--fix option only valid with --check.")

    def _validate_extra_arguments(self, extra_args):
        self.extra_args = list(set(extra_args) - {"--no-nose", "-s"})
        unrecognized = [ea for ea in self.extra_args if ea.startswith("-")]
        if unrecognized:
            self.parser.error(f'unrecognized arguments: {", ".join(unrecognized)}')
        if "-s" in extra_args:
            self.out("WARNING: The -s option is deprecated/no longer used.")

    def _run(self, args):
        success = True
        if args.fetch:
            with FetchMode(args, self.extra_args) as fetch:
                # Handle fetcher primary run.
                self.out("\nFetcher Primary Run\n")
                success = fetch.run_fetchers()
                # Handle fetcher dependency reruns.
                previous = set()
                reruns = fetch.locker.get_dependency_reruns()
                rerun_count = 1
                while reruns and reruns != previous and rerun_count <= 100:
                    # Upper bound for reruns set to 100
                    # to guard against endless executions.
                    self.out(f"\nFetcher Dependency Re-Run #{rerun_count}\n")
                    success = fetch.run_fetchers(reruns) and success
                    rerun_count += 1
                    previous = reruns
                    reruns = fetch.locker.get_dependency_reruns()
                if reruns:
                    success = False
                    self.err(
                        "\nUnable to resolve dependency issues with %s.\n",
                        ", ".join(reruns),
                    )
                for fetch_load_error in fetch.load_errors:
                    self.err(f"\nERROR: {fetch_load_error}\n")
        if args.check:
            with CheckMode(args, self.extra_args) as check:
                accreds = ", ".join(check.accreds)
                self.out(f"\nCheck Run - Accreditations: {accreds}\n")
                success = check.run_checks() and success
                for check_load_error in check.load_errors:
                    self.err(f"\nERROR: {check_load_error}\n")
        return 0 if success else 1


def run():
    """Execute the Compliance CLI."""
    exit(ComplianceCLI().run())


if __name__ == "__main__":
    run()
