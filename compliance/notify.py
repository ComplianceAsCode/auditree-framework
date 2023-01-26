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
"""Compliance notification management automation module."""

import copy
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import PurePath
from urllib.parse import urlparse

from compliance.config import get_config
from compliance.utils.services import pagerduty
from compliance.utils.services.github import Github
from compliance.utils.test import parse_test_id

from ibm_cloud_sdk_core.api_exception import ApiException
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

from ibm_cloud_security_advisor import FindingsApiV1

import requests


class _BaseNotifier(object):
    """
    Base notifier class.

    It shouldn't be used outside of this module.
    """

    def __init__(self, results, controls, push_error):
        self._results = results
        self._controls = controls
        self._push_error = push_error
        self.logger = logging.getLogger(name="compliance.notifier")
        self._handler = logging.StreamHandler()
        self._handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        self.logger.handlers.clear()
        self.logger.addHandler(self._handler)
        self.logger.setLevel(logging.INFO)

    @property
    def messages(self):
        """
        Check test messages.

        A generator of list of tuples containing the following structure::

          ([str] test_id, [dict] test_descriptor, [dict] message)
        """
        for test_id, test_desc in self._results.items():
            test_obj = test_desc["test"].test
            method_name = parse_test_id(test_id)["method"]

            msg_method = "get_notification_message"
            if len(test_obj.tests) > 1:
                candidate = method_name.replace("test_", "msg_", 1)
                if hasattr(test_obj, candidate):
                    msg_method = candidate

            # set body to None if the notification function hasn't been
            # defined or if it returns None.
            # use a predefined error message for error status.
            # otherwise get the results of the notification function.
            # note that passed tests get their notifications called in order to
            # deduce things like subtitle, but their notifications are not
            # displayed.
            if not hasattr(test_obj, msg_method):
                msg = None
                body = None
            elif test_desc["status"] == "error":
                msg = None
                body = f"Check {test_id} failed to execute"
            elif len(test_obj.tests) > 1 and not msg_method.startswith("msg_"):
                msg = getattr(test_obj, msg_method)(method_name)
                body = msg and "body" in msg and msg["body"] or None
            else:
                msg = getattr(test_obj, msg_method)()
                body = msg and "body" in msg and msg["body"] or None

            title = test_obj.title
            if msg and "subtitle" in msg and msg["subtitle"]:
                title += f' - {msg["subtitle"]}'

            failure_count = 0
            if msg and test_obj.failures:
                failure_count = test_obj.failures_count()

            warning_count = 0
            if msg and test_obj.warnings:
                warning_count = test_obj.warnings_count()

            msg = {
                "title": title,
                "body": body,
                "failure_count": failure_count,
                "warning_count": warning_count,
            }
            yield test_id, test_desc, msg

    def _messages_by_accreditations(self):
        retval = {}
        for test_id, test_desc, msg in self.messages:
            test_class = parse_test_id(test_id)["class_path"]
            accreditations = self._controls.get_accreditations(test_class)
            for a in accreditations:
                messages = retval.get(a, [])
                messages.append((test_id, test_desc, msg))
                retval[a] = messages
        return retval

    def _split_by_status(self, messages):
        passed_tests = []
        failed_tests = []
        warned_tests = []
        errored_tests = []
        sorted_msgs = sorted(messages, key=lambda x: x[2]["title"])
        for test_id, test_desc, msg in sorted_msgs:
            if test_desc["status"] == "pass":
                passed_tests.append((test_id, test_desc, msg))
            elif test_desc["status"] == "error":
                errored_tests.append((test_id, test_desc, msg))
            elif test_desc["status"] == "warn":
                warned_tests.append((test_id, test_desc, msg))
            else:
                failed_tests.append((test_id, test_desc, msg))
        return passed_tests, failed_tests, warned_tests, errored_tests

    def _get_check_names(self, checks, include_path=False):
        if include_path:
            return [(msg["title"], path) for path, _, msg in checks]
        return [msg["title"] for _, _, msg in checks]

    def _get_report_links(self, test_desc, link_format=None):
        if not link_format:
            link_format = "<{url}|{name}>"

        if test_desc["status"] == "error":
            return []

        test_obj = test_desc["test"].test

        return [
            link_format.format(
                url=test_obj.locker.get_remote_location(report.path), name=report.name
            )
            for report in test_obj.reports
        ]

    def _get_summary_and_body(
        self, test_desc, msg, include_title=True, summary_format=None, link_format=None
    ):
        link_format = link_format or "<{url}|{name}>"
        if not summary_format:
            summary_format = ""
            if include_title:
                summary_format += "{title} - "
            summary_format += "{status} ({issues}) " "Reports: {reports} {runbook}"

        test_obj = test_desc["test"].test

        issues_list = []
        if msg["failure_count"] > 0:
            issues_list.append(f'{msg["failure_count"]} failures')
        if msg["warning_count"] > 0:
            issues_list.append(f'{msg["warning_count"]} warnings')
        if test_obj.fixed_failure_count > 0:
            issues_list.append(f"{test_obj.fixed_failure_count} fixed")

        issues = ", ".join(issues_list)
        report_links = self._get_report_links(test_desc, link_format)
        if not report_links:
            report_links.append("(none)")

        runbook_conditional = ""
        if test_obj.runbook_url:
            runbook_conditional = "| " + link_format.format(
                url=test_obj.runbook_url, name="Run Book"
            )

        summary_line = summary_format.format(
            title=msg["title"],
            status=test_desc["status"].upper(),
            issues=issues,
            reports=", ".join(report_links),
            runbook=runbook_conditional,
        )

        body = msg["body"] and f'\n{msg["body"]}' or ""

        return summary_line, body


class _BaseMDNotifier(_BaseNotifier):
    """
    Base markdown notifier class.

    It shouldn't be used outside of this module.
    """

    def __init__(self, results, controls, push_error):
        super(_BaseMDNotifier, self).__init__(results, controls, push_error)

    def _generate_accred_content(self, accred, results, skip_title=False):
        md_content = []
        if not skip_title:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            md_content.append(f"# CHECK RESULTS: {now}")
        md_content.append(f"\n## Notification for {accred.upper()} accreditation\n")
        if self._push_error:
            md_content.append("### All Checks (Errored)\n")
            md_content.append(
                "   - Evidence/Results failed to push to remote locker.  "
                "See execution log for details."
            )
        else:
            for heading in ["Passed Checks", "Errored Checks"]:
                md_content.append(f"### {heading}\n")
                checks = self._get_check_names(
                    results[heading[:-9].lower()], include_path=True
                )
                if checks:
                    check_title = None
                    for check in checks:
                        if check[0] != check_title:
                            md_content.append(f"- **{check[0]}**")
                            check_title = check[0]
                        if heading == "Errored Checks":
                            md_content.append(f"   - {check[1]} failed to execute")
                else:
                    md_content.append(f"- **No {heading.lower()}**")
            md_content.append("### Failures/Warnings\n")
            fail_and_warn = results["fail"] + results["warn"]
            if fail_and_warn:
                summary_format = [
                    "- **{title}**",
                    "   - **{status}** | {reports} {runbook}",
                    "   - {issues}",
                ]
                rpt_link_format = "[{name}]({url})"
                for _, test_desc, msg in fail_and_warn:
                    summary, addl_content = self._get_summary_and_body(
                        test_desc,
                        msg,
                        summary_format="\n".join(summary_format),
                        link_format=rpt_link_format,
                    )
                    md_content.append(summary)
                    if addl_content:
                        for line in addl_content.strip().split("\n"):
                            md_content.append(f"   - _{line}_")
            else:
                md_content.append("- **No failures or warnings**")
        return md_content


class FDNotifier(_BaseNotifier):
    """
    File descriptor notifier class.

    Notifications are written to the file descriptor specified.
    Defaults to STDOUT.
    """

    def __init__(self, results, controls, fd=sys.stdout, push_error=False):
        """
        Construct and initialize the file descriptor notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        :param fd: a file descriptor where to write the notifications on.
          Defaults to STDOUT.
        """
        super(FDNotifier, self).__init__(results, controls, push_error)
        self.fd = fd

    def notify(self):
        """Write notifications into the file descriptor."""
        self.logger.info("Running the STDOUT notifier...")
        self.fd.write("\n-- NOTIFICATIONS --\n\n")
        if not self._results:
            self.fd.write("No results\n")
        elif self._push_error:
            self.fd.write(
                "All accreditation checks:  "
                "Evidence/Results failed to push to remote locker.\n"
            )
        else:
            accreds = []
            messages = list(self._messages_by_accreditations().items())
            messages.sort(key=lambda x: x[0])
            for accreditation, msgs in messages:
                if not msgs:
                    continue
                passed, failed, warned, errored = self._split_by_status(msgs)
                accreds.append(
                    {
                        "name": accreditation,
                        "passed": passed,
                        "failed": failed,
                        "warned": warned,
                        "errored": errored,
                    }
                )
            for accred in accreds:
                self.fd.write(
                    f'Notifications for {accred["name"].upper()} ' "accreditation\n\n"
                )
                passed_msg = (
                    ", ".join(self._get_check_names(accred["passed"])) or "(none)"
                )
                accred_msgs = [f"PASSED checks: {passed_msg}"]
                for msg_type in ["errored", "warned", "failed"]:
                    accred_msgs.append(
                        "\n\n".join(
                            [
                                "".join(self._get_summary_and_body(test_desc, msg))
                                for (_, test_desc, msg) in accred[msg_type]
                            ]
                        )
                    )
                self.fd.write("\n\n".join(accred_msgs) + "\n\n")
        self.fd.flush()


class LockerNotifier(_BaseMDNotifier):
    """
    Evidence Locker notifier class.

    Notifications are written to the evidence locker.

    :param results: dictionary generated by
      :py:class:`compliance.runners.CheckMode` at the end of the execution.
    :param controls: dictionary of checks and the accreditations and controls
      that they belong to.
    """

    def __init__(self, results, controls, locker, push_error=False):
        """
        Construct and initialize the evidence locker notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        :param locker: the evidence locker object.
        """
        super(LockerNotifier, self).__init__(results, controls, push_error)
        self.locker = locker

    def notify(self):
        """Write notifications into the evidence locker."""
        if not self._results:
            self.logger.error("No results.  Locker notifier not triggered.")
            return
        if self._push_error:
            self.logger.error(
                "Remote locker push failed.  Locker notifier not triggered."
            )
            return
        self.logger.info("Running the Locker notifier...")
        messages = list(self._messages_by_accreditations().items())
        messages.sort(key=lambda x: x[0])
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        md_content = [f"# CHECK RESULTS: {now}"]
        for accreditation, results in messages:
            passed, failed, warned, errored = self._split_by_status(results)
            results_by_status = {
                "pass": passed,
                "fail": failed,
                "warn": warned,
                "error": errored,
            }
            md_content.extend(
                self._generate_accred_content(
                    accreditation, results_by_status, skip_title=True
                )
            )
        folder = "notifications"
        filename = "alerts_summary.md"
        self.locker.add_content_to_locker("\n".join(md_content), folder, filename)
        self.locker.checkin(
            "Locker notification sent at local time "
            f"{time.ctime(time.time())}\n\n{PurePath(folder, filename)}"
        )
        self.locker.push()


class GHIssuesNotifier(_BaseMDNotifier):
    """
    Github notifier class.

    Notifications are sent to Github as repository issues.  This
    notifier is configurable via :class:`compliance.config.ComplianceConfig`.
    """

    def __init__(self, results, controls, push_error=False):
        """
        Construct and initialize the Github notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        """
        super(GHIssuesNotifier, self).__init__(results, controls, push_error)

        self._config = get_config().get("notify.gh_issues")
        if not self._config:
            # Ensure that legacy ghe_issues config still works
            self._config = get_config().get("notify.ghe_issues", {})
        # Using the locker repo url to define the base url.  The expectation
        # is that the Github issues repository will share the base url.
        parsed_locker_url = urlparse(get_config().get("locker.repo_url"))
        self._github = Github(
            get_config().creds,
            f"{parsed_locker_url.scheme}://{parsed_locker_url.hostname}",
        )

    def notify(self):
        """Send notifications to Github as repository issues."""
        self.logger.info("Running the Github Issues notifier...")
        if not self._config:
            self.logger.warning("Using Github Issues notifier without config")

        messages = list(self._messages_by_accreditations().items())
        messages.sort(key=lambda x: x[0])
        for accreditation, results in messages:
            if accreditation not in self._config:
                continue
            passed, failed, warned, errored = self._split_by_status(results)
            results_by_status = {
                "pass": passed,
                "fail": failed,
                "warn": warned,
                "error": errored,
            }
            if self._config[accreditation].get("summary_issue"):
                self._notify_by_summary_issue(accreditation, results_by_status)
            elif self._push_error:
                self.logger.error(
                    "Remote locker push failed.  "
                    "Github Issues notifier not triggered."
                )
            else:
                self._notify_by_check_issues(accreditation, results_by_status)

    def _notify_by_summary_issue(self, accred, results):
        issue = [self._generate_summary_issue(accred, results)]
        repos = self._config[accred].get("repo", [])
        for repo in repos:
            owner, repository = repo.split("/")
            issue_urls = self._process_new_alerts(
                owner,
                repository,
                issue,
                self._config[accred]["summary_issue"].get("message"),
            )
            self._assign_projects(issue_urls, repo, accred)

    def _generate_summary_issue(self, accred, results):
        summary_config = self._config[accred]["summary_issue"]
        title = summary_config["title"]
        labels = summary_config.get("labels", [])
        assignees = summary_config.get("assignees", [])
        frequency = summary_config.get("frequency")
        rotation = summary_config.get("rotation")
        rotation_index = None
        now = datetime.utcnow()
        if frequency == "day":
            today = now.strftime("%Y-%m-%d")
            title = f"{today} - {title}"
            labels.extend([frequency, today])
            rotation_index = now.timetuple().tm_yday
        elif frequency == "week":
            year, week, _ = now.isocalendar()
            title = f"{year}, {week}W - {title}"
            labels.extend([frequency, str(year), f"{week}W"])
            rotation_index = week
        elif frequency == "month":
            year = now.strftime("%Y")
            month = now.strftime("%mM")
            title = f"{year}, {month} - {title}"
            labels.extend([frequency, year, month])
            rotation_index = int(month[:-1])
        elif frequency == "year":
            year = now.strftime("%Y")
            title = f"{year} - {title}"
            labels.extend([frequency, year])
            rotation_index = int(year)
        if rotation and rotation_index:
            assignees = rotation[divmod(rotation_index, len(rotation))[1]]
        issue = {"title": title, "labels": labels, "assignees": assignees}
        issue["body"] = "\n".join(self._generate_accred_content(accred, results))
        return issue

    def _notify_by_check_issues(self, accred, results):
        issues = []
        statuses = self._config[accred].get("status", ["fail"])
        repos = self._config[accred].get("repo", [])
        for status, result in results.items():
            if status in statuses:
                issues += self._generate_issues(accred, result)
        for repo in repos:
            owner, repository = repo.split("/")
            issue_urls = self._process_new_alerts(owner, repository, issues)
            self._assign_projects(issue_urls, repo, accred)
        if "pass" not in statuses:
            for repo in repos:
                owner, repository = repo.split("/")
                issues = self._generate_issues(accred, results["pass"])
                issue_urls = self._process_old_alerts(owner, repository, issues)
                self._assign_projects(issue_urls, repo, accred)

    def _generate_issues(self, accred, results):
        issues = []
        if not results:
            return issues
        for check_path, result, message in results:
            # If the 'checks' configuration element exists
            # within an accreditation, only create issues
            # for the set of checks therein.
            if (
                "checks" in self._config[accred].keys()
                and check_path not in self._config[accred]["checks"]
            ):
                continue
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            body = [f"## Compliance check alert - {now}"]
            body.append(f"- Check: {check_path}")
            test_obj = result["test"].test
            check_name = check_path.rsplit(".", 1).pop()
            doc = getattr(test_obj.__class__, check_name).__doc__
            if doc:
                doc = doc.strip()
                newline = doc.find("\n")
                if newline > -1:
                    doc = doc[:newline]
                body.append(f"- Description: {doc}")
            body.append(f"- Accreditation: {accred}")
            status = "".join(
                self._get_summary_and_body(
                    result,
                    message,
                    include_title=False,
                    summary_format="{status} ({issues})",
                    link_format="[{name}]({url})",
                )
            )
            body.append(f"- Run Status: **{status}**")
            run_dttm = datetime.fromtimestamp(result["timestamp"])
            body.append(f"- Run Date/Time: {run_dttm}")
            report_links = self._get_report_links(result, link_format="[{name}]({url})")
            if report_links:
                body.append(f'- Reports: {", ".join(report_links)}')

            issue = {
                "title": message["title"],
                "body": "\n".join(body),
                "labels": [
                    f"accreditation: {accred}",
                    f'run status: {result["status"]}',
                ],
            }
            issues.append(issue)

        return issues

    def _process_new_alerts(self, owner, repository, issues, message=None):
        issue_urls = {}
        for issue in issues:
            gh_issue = self._find_gh_issue(
                "/".join([owner, repository]), issue["title"]
            )
            if gh_issue is None:
                body = issue["body"]
                if message:
                    joined_msg = "\n".join(message)
                    body = f'{joined_msg}\n\n{issue["body"]}'
                gh_issue = self._github.add_issue(
                    owner,
                    repository,
                    issue["title"],
                    body,
                    labels=issue["labels"],
                    assignees=issue.get("assignees", []),
                )
            else:
                self._update_issue_labels(owner, repository, gh_issue, issue["labels"])
                self._github.add_issue_comment(
                    owner, repository, gh_issue["number"], issue["body"]
                )
            issue_urls[gh_issue["id"]] = gh_issue["url"]
        return issue_urls

    def _process_old_alerts(self, owner, repository, issues):
        issue_urls = {}
        for issue in issues:
            gh_issue = self._find_gh_issue(
                "/".join([owner, repository]), issue["title"]
            )
            if gh_issue:
                self._update_issue_labels(owner, repository, gh_issue, issue["labels"])
                self._github.add_issue_comment(
                    owner, repository, gh_issue["number"], issue["body"]
                )
                issue_urls[gh_issue["id"]] = gh_issue["url"]
        return issue_urls

    def _find_gh_issue(self, repo, title):
        gh_issues = self._github.search_issues(
            f"{title} type:issue in:title is:open repo:{repo}"
        )
        found = None
        for issue in gh_issues:
            if issue["title"] == title:
                found = issue
                break
        return found

    def _update_issue_labels(self, owner, repository, issue, labels):
        current_labels = [label["name"] for label in issue["labels"]]
        new_labels = list(set(labels) - set(current_labels))
        if new_labels:
            current_labels = [
                label
                for label in current_labels
                if not label.startswith("run status: ")
            ]
            self._github.patch_issue(
                owner, repository, issue["number"], labels=current_labels + new_labels
            )

    def _assign_projects(self, issues, repo, accred):
        config_projects = self._config[accred].get("project")
        if not config_projects:
            return
        all_projects = {p["name"]: p["id"] for p in self._github.get_all_projects(repo)}
        for project, column in config_projects.items():
            if project not in all_projects.keys():
                self.logger.warning(f"Project {project} not found in {repo}")
                continue
            columns = {
                c["name"]: c["id"]
                for c in self._github.get_columns(all_projects[project])
            }
            if column not in columns.keys():
                self.logger.warning(
                    f"Column {column} not found " f"in {project} project, {repo} repo"
                )
                continue
            card_lists = self._github.get_all_cards(columns.values()).values()
            issue_urls = [c.get("content_url") for cl in card_lists for c in cl]
            for issue_id, issue_url in issues.items():
                if issue_url in issue_urls:
                    continue
                self._github.add_card(columns[column], issue=issue_id)


class SlackNotifier(_BaseNotifier):
    """
    Slack notifier class.

    Notifications are sent to Slack channel(s).  This notifier is
    configurable via :class:`compliance.config.ComplianceConfig`.
    """

    MESSAGE_COLORS = {
        "pass": "#00D000",
        "fail": "#D00000",
        "error": "#9932CC",
        "warn": "#FFD300",
    }

    def __init__(self, results, controls, push_error=False):
        """
        Construct and initialize the Slack notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        """
        super(SlackNotifier, self).__init__(results, controls, push_error)
        self._creds = get_config().creds
        self._config = get_config().get("notify.slack", {})

    def notify(self):
        """Send notifications to Slack channel(s)."""
        self.logger.info("Running the Slack notifier...")
        if not self._config:
            self.logger.warning("Using Slack notifier without config")

        messages = list(self._messages_by_accreditations().items())
        messages.sort(key=lambda x: x[0])
        for accreditation, desc in messages:
            if accreditation not in self._config:
                continue
            channels = []
            mode = "normal"
            if isinstance(self._config[accreditation], list):
                channels = self._config[accreditation]
            elif isinstance(self._config[accreditation], dict):
                channels = self._config[accreditation].get("channels", [])
                rotation = self._config[accreditation].get("rotation")
                mode = self._config[accreditation].get("mode", "normal")
                if rotation and isinstance(rotation, list):
                    iso_week = datetime.utcnow().isocalendar()[1]
                    on_duty = rotation[divmod(iso_week, len(rotation))[1]]
                    if isinstance(on_duty, dict):
                        channels.append(on_duty.get("id"))
                    else:
                        channels.append(on_duty)
            msg = self._generate_message(accreditation, desc, mode=mode)
            self._send_message(msg, channels)

    def _generate_message(self, accreditation, test_descs, mode="normal"):
        if not test_descs:
            return {}
        text = (
            f"Notification for {accreditation.upper()} accreditation "
            f'at {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}'
        )
        message = {
            "username": "Compliance Alerts",
            "icon_emoji": ":robot_face:",
            "text": text,
        }
        modes = {
            "normal": self._generate_normal_attachments,
            "compact": self._generate_compact_attachments,
        }
        if mode in modes.keys():
            if self._push_error:
                message["attachments"] = self._generate_push_error_attachment()
            else:
                message["attachments"] = modes[mode](test_descs)
        else:
            raise ValueError(f"Unknown Slack message mode: {mode}")
        return message

    def _generate_push_error_attachment(self):
        return [
            {
                "title": "ALL checks",
                "text": (
                    "Evidence/Results failed to push to remote locker.  "
                    "See execution log for details."
                ),
                "mrkdwn_in": ["text", "pretext"],
                "color": SlackNotifier.MESSAGE_COLORS["error"],
            }
        ]

    def _generate_normal_attachments(self, test_descs):
        retval = []
        passed, failed, warned, errored = self._split_by_status(test_descs)

        # first list each error, failure, and warning
        for _, test_desc, msg in errored + failed + warned:
            text = "".join(
                self._get_summary_and_body(test_desc, msg, include_title=False)
            )

            attachment = {
                "title": msg["title"],
                "text": text,
                "mrkdwn_in": ["text", "pretext"],
                "color": SlackNotifier.MESSAGE_COLORS[test_desc["status"]],
            }
            retval.append(attachment)

        # then have a list of passed checks
        passed_titles = self._get_check_names(passed)
        if not passed_titles:
            passed_titles.append("(none)")
        retval.append(
            {
                "title": "PASSED checks",
                "text": ", ".join(passed_titles),
                "mrkdwn_in": ["text", "pretext"],
                "color": SlackNotifier.MESSAGE_COLORS["pass"],
            }
        )

        return retval

    def _generate_compact_attachments(self, test_descs):
        retval = []
        passed, failed, warned, errored = self._split_by_status(test_descs)

        # passed tests
        if passed:
            retval.append(
                {
                    "title": f"PASS: {len(passed)} checks",
                    "text": "",
                    "mrkdwn_in": ["text", "pretext"],
                    "color": SlackNotifier.MESSAGE_COLORS["pass"],
                }
            )

        # warned and failed tests
        collections = [("warn", warned), ("fail", failed)]
        fmt = "{title} - {reports} {runbook} - ({issues})"
        for status, c in collections:
            text = ""
            for _, test_desc, msg in c:
                summary, body = self._get_summary_and_body(
                    test_desc, msg, include_title=False, summary_format=fmt
                )
                text += "* " + summary
                if body:
                    text += " - " + "; ".join(
                        body.strip().replace("Failures:", "").split("\n")
                    )
                text += "\n"
            if text:
                attachment = {
                    "title": f"{status.upper()}: {len(c)} checks",
                    "text": text.strip(),
                    "mrkdwn_in": ["text", "pretext"],
                    "color": SlackNotifier.MESSAGE_COLORS[status],
                }
                retval.append(attachment)

        # errors tests
        if errored:
            retval.append(
                {
                    "title": f"ERRORS: {len(errored)} checks",
                    "text": ", ".join(set(self._get_check_names(errored))),
                    "mrkdwn_in": ["text", "pretext"],
                    "color": SlackNotifier.MESSAGE_COLORS["error"],
                }
            )
        return retval

    def _send_message(self, message, channels):
        msg = copy.deepcopy(message)
        for c in channels:
            msg["channel"] = c
            headers = {}
            url = getattr(self._creds["cloobot"], "webhook", None) or getattr(
                self._creds["slack"], "webhook", None
            )
            if not url:
                token = getattr(self._creds["cloobot"], "token", None) or getattr(
                    self._creds["slack"], "token", None
                )
                if token is None:
                    raise RuntimeError(
                        "Unable to get a Slack webhook or token from "
                        "credentials file"
                    )
                url = "https://slack.com/api/chat.postMessage"
                headers["Authorization"] = "Bearer " + token
                headers["Content-type"] = "application/json"
            retries = self._config.get("retries", 3)
            retry = 0
            while retry < retries:
                response = requests.post(url, headers=headers, data=json.dumps(msg))
                if response.status_code == 429:
                    time.sleep(int(response.headers.get("Retry-After", retry)) + 1)
                    retry += 1
                else:
                    response.raise_for_status()
                    break


class PagerDutyNotifier(_BaseNotifier):
    """PagerDuty notifier class."""

    def __init__(self, results, controls, push_error=False):
        """
        Construct and initialize the PagerDuty notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        """
        super(PagerDutyNotifier, self).__init__(results, controls, push_error)
        self._creds = get_config().creds
        self._config = get_config().get("notify.pagerduty", {})

    def notify(self):
        """Send notifications as PagerDuty alerts."""
        if self._push_error:
            self.logger.error(
                "Remote locker push failed.  PagerDuty notifier not triggered."
            )
            return
        self.logger.info("Running the PagerDuty notifier...")
        if not self._config:
            self.logger.warning("Using PagerDuty notifier without config")

        # get all checks by accreditation
        messages = list(self._messages_by_accreditations().items())
        messages.sort(key=lambda x: x[0])
        for accreditation, desc in messages:
            if accreditation not in self._config or not desc:
                continue
            # determine if we should page for all failing checks in this
            # accreditation, or only a subset defined in the config.
            # The config can either be a string of the PD service ID,
            # or a dictionary containing additional config details, including
            # the optional list of checks.
            all_checks, pd_checks = True, []
            if (
                isinstance(self._config[accreditation], dict)
                and "checks" in self._config[accreditation]
            ):
                all_checks = False
                pd_checks = self._config[accreditation]["checks"] or []

            # get all current PD alerts
            alerts = self._get_alerts(accreditation)

            # fail/error will trigger alerts, and pass/warn will clear them
            passed, failed, warned, errored = self._split_by_status(desc)

            for test_id, test_desc, msg in failed + errored:
                # is the check in scope?
                if not all_checks and test_id not in pd_checks:
                    continue

                summary, body = self._get_summary_and_body(
                    test_desc, msg, summary_format="{status} ({issues})"
                )
                details = summary + body

                # don't trigger an alert if it's already in PD, unless its
                # details have changed
                existing_alert = next((a for a in alerts if a["test"] == test_id), None)
                if existing_alert and existing_alert["details"] == details:
                    continue

                if existing_alert:
                    self._update_alert(test_id, test_desc, msg, accreditation, details)
                else:
                    self._trigger_alert(test_id, test_desc, msg, accreditation, details)

            for test_id, test_desc, msg in passed + warned:
                # don't resolve an alert if it isn't in PD
                existing_alert = next((a for a in alerts if a["test"] == test_id), None)
                if not existing_alert:
                    continue

                self._resolve_alert(test_id, test_desc, msg, accreditation)

    def _get_alerts(self, accreditation):
        conf = self._config[accreditation]
        pd_service = conf["service_id"] if isinstance(conf, dict) else conf

        # Get all current incidents for the service, we need to specify both
        # acknowledged and triggered so we do not send a second page if there
        # has already been one acknowledged
        incidents_data = pagerduty.get(
            "incidents",
            params={
                "service_ids[]": pd_service,
                "statuses[]": ["acknowledged", "triggered"],
                "time_zone": "UTC",
            },
            creds=self._creds,
        )
        alerts = []

        # If there are any incidents then loop through them and fetch all the
        # alerts that are related to the service
        for inc_data in incidents_data:
            inc_data.raise_for_status()
            incidents = inc_data.json()["incidents"]
            for inc in incidents:
                alerts_data = pagerduty.get(
                    f'incidents/{inc["id"]}/alerts',
                    params={
                        "service_ids[]": pd_service,
                        "statuses[]": ["acknowledged", "triggered"],
                        "time_zone": "UTC",
                    },
                    creds=self._creds,
                )
                # Fetch all alerts for the incidents
                for alert_data in alerts_data:
                    alert_data.raise_for_status()
                    alerts += [
                        {
                            "test": a["alert_key"],
                            "details": a.get("body", {}).get("details", ""),
                            "created_at": a["created_at"],
                        }
                        for a in alert_data.json()["alerts"]
                    ]
        # if more than one alert is listed for a check, only return the latest
        latest_alerts = []
        alerts.sort(key=lambda alert: alert["created_at"], reverse=True)
        for alert in alerts:
            alert_short = {"test": alert["test"], "details": alert["details"]}
            if alert_short not in latest_alerts:
                latest_alerts.append(alert_short)
        return latest_alerts

    def _trigger_alert(self, test_id, test_desc, msg, accreditation, details):
        report_links = self._get_report_links(
            test_desc, link_format="Report: {name}|{url}"
        )
        links = [
            {"text": t, "href": rl} for t, rl in [rl.split("|") for rl in report_links]
        ]

        if test_desc["test"].test.runbook_url:
            links.append(
                {"text": "Runbook", "href": test_desc["test"].test.runbook_url}
            )

        pagerduty.send_event(
            action="trigger",
            check=test_id,
            title=msg["title"],
            source=accreditation,
            severity="error",
            details=details,
            links=links,
            creds=self._creds,
        )

    def _update_alert(self, test_id, test_desc, msg, accreditation, details):
        # NOTE: Unfortunately the PD API v2 doesn't have any way
        #       that I've found to actually update an existing alert
        #       or incident. A new log entry with the details is added
        #       but is hidden away. The visible info when you click on
        #       an incident remains as it was when it was first
        #       triggered.
        #       We can work around this by resolving the incident and
        #       then opening a new one.
        self._resolve_alert(test_id, test_desc, msg, accreditation)
        self._trigger_alert(test_id, test_desc, msg, accreditation, details)

    def _resolve_alert(self, test_id, test_desc, msg, accreditation):
        pagerduty.send_event(
            action="resolve",
            check=test_id,
            title=msg["title"],
            source=accreditation,
            severity="error",
            creds=self._creds,
        )


class FindingsNotifier(_BaseNotifier):
    """
    Findings notifier class.

    Notifications are sent using the Findings API.  This notifier is
    configurable via :class:`compliance.config.ComplianceConfig`.
    """

    def __init__(self, results, controls, push_error=False):
        """
        Construct and initialize the Findings notifier object.

        :param results: dictionary generated by
          :py:class:`compliance.runners.CheckMode` at the end of the execution.
        :param controls: the control descriptor that manages accreditations.
        """
        super(FindingsNotifier, self).__init__(results, controls, push_error)
        self._config = get_config().get("notify.findings")
        self._creds = get_config().creds
        api_key = self._creds["findings"].api_key
        authenticator = IAMAuthenticator(apikey=api_key)
        self.findings_api = FindingsApiV1(authenticator=authenticator)

    def notify(self):
        """Send notifications to the Findings API."""
        if self._push_error:
            self.logger.error(
                "Remote locker push failed.  Findings notifier not triggered."
            )
            return
        self.logger.info("Running the Findings notifier...")
        if not self._config:
            self.logger.warning("Using findings notification without config")

        messages = list(self._messages_by_accreditations().items())
        messages.sort(key=lambda x: x[0])
        for accreditation, desc in messages:
            if accreditation not in self._config:
                continue
            findings_api_endpoint = self._config[accreditation]
            self.findings_api.set_service_url(findings_api_endpoint)

            passed, failed, warned, errored = self._split_by_status(desc)
            for _, _, msg in failed + errored + passed + warned:
                self._create_findings(msg["body"])

    def _create_findings(self, data):
        occurrence_list = data["occurrence_list"]
        account_id = data["account_id"]
        provider_id = data["provider_id"]
        status = 0

        for occurrence in occurrence_list:
            try:
                response = self.findings_api.create_occurrence(
                    account_id=account_id, provider_id=provider_id, **occurrence
                )
                self.logger.info(response.status_code)
            except ApiException as e:
                status = e.code
                self.logger.error(
                    "Finding creation failed "
                    f'for occurrence id {occurrence["id"]} '
                    f"with {str(e.code)}: {str(e)}"
                )
            except Exception as e:
                status = -1
                self.logger.error(f"Unexpected error occurred: {str(e)}")
        return status


def get_notifiers():
    """
    Provide a dictionary of all notifier class objects.

    This dictionary contains all valid notifier choices for the ``--notify``
    option in the CLI as keys and their corresponding notifier classes as
    values.

    NOTE: When adding/removing a notifier, update this dictionary accordingly.
    """
    return {
        "stdout": FDNotifier,
        "slack": SlackNotifier,
        "pagerduty": PagerDutyNotifier,
        "gh_issues": GHIssuesNotifier,
        "locker": LockerNotifier,
        "findings": FindingsNotifier,
    }
