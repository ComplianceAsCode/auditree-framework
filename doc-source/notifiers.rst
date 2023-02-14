.. -*- mode:rst; coding:utf-8 -*-

.. _notifiers-description:

Notifiers
=========

The last phase in a typical framework check run is the notification
system.  Multiple notifiers can be targeted as part of this phase by using
the ``--notify`` option on the ``compliance --check`` command.  Valid
notifier options are ``stdout``, ``slack``, ``pagerduty``, ``findings``,
``gh_issues`` and, ``locker``.  The general idea behind the notification
system is that each ``test_`` can generate a short notification that has the
following components:

    **NOTE:** When configuring notifiers, you should be aware of the
    possibility that notifications may contain sensitive information that can be
    sent to less trusted stores like Slack or public git issue trackers. So be
    mindful of check notification content as well as the nature of the forum
    you intend to send these notifications to.

* title (mandatory): should be a ``property`` of the
  ``ComplianceCheck``:

  .. code-block:: python

     @property
     def title(self):
         return 'The title'

* body (mandatory): the body of the message.

* subtitle (optional): if the check has several ``test_`` methods,
  then you can use subtitle in order to distinguish them when all
  notifications are sent.

If you want to create a notification for a given check, use one of the
following strategies:

* If your ``ComplianceCheck`` only has one ``test_`` method, you should
  just implement a ``get_notification_message()`` method in your check.

* If there are many ``test_`` methods, you can either:

  - Implement ``get_notification_message(test_id)`` and generate the
    notification structure based on the ``test_id`` parameter.

  - Implement ``msg_<name-of-the-check>()`` method. For example, if one of your
    test methods is named ``test_ssh_users()`` then you will need to implement
    a check notification method named ``msg_ssh_users()``.

All check notification methods must return a dictionary with the following
structure::

  {
    "subtitle": "The subtitle of the check"  # if required/desired,
    "body": "The body message"  # if None, use a standard body
  }

When possible, it is recommended to use the standard body message
``{"body": None}`` which includes the number of failures, the number of
warnings, the number of issues fixed by fixers (if applicable), links to report
evidences generated (if applicable) and a link to the check runbook that
contains remediation instructions (if applicable).

The following sections describe the notifiers supported by the framework.

File descriptor
---------------

File descriptor notifications are written directly to standard output.  Among
other things, this is useful for testing purposes.  The file descriptor
notifier is also the default notifier and does not need to be specifically
set using the ``--notify`` command line parameter.

Notifications are grouped by accreditation and check result (passing, warning,
failure, error).

Slack
-----

This configurable notifier will notify Slack channels (including user personal
channels if desired) per accreditation.  If configured, it will also manage
a channel monitoring rotation that will select the appropriate user for the
current week and direct message them for a given accreditation.  The following
is an example configuration for this notifier to be added to a configuration
file and used with the ``-C`` option when executing your compliance checks::

  "notify": {
    "slack": {
      "accred.one": {
        "channels": ["#alert_channel_alpha", "#alert_channel_beta"],
        "rotation": ["@foo", "@bar", "@baz"]
      },
      "accred.two": {
        "channels": ["#alert_channel_gamma"],
        "rotation": ["@moe", "@larry", "@curly"],
        "mode": "compact"
      }
    }
  }

Note that you can select the ``mode`` of the notification. ``slack``
notificator offers the following modes:

- ``normal``: includes all types of test results (pass, fail, error,
  and warning) as well as a full description of each test. This is the
  default mode.

- ``compact``: show all types of test results but only show details on
  errors and warnings.

The below configuration format is also valid but does not provide for
channel monitoring rotation management::

  {
    "notify": {
      "slack": {
        "accred.one": ["#alert_channel_alpha", "#alert_channel_beta"],
        "accred.two": ["@shemp"]
      }
    }
  }


This notifier also needs to know the credentials for sending message
to your Slack organization. Include the following in your credentials
file::

  [slack]
  webhook=XXX

You can also use a Slack app token (recommended if you need to post
messages to private channels)::

  [slack]
  token=XXX

Note that you can do the same thing using env vars ``SLACK_WEBHOOK`` and ``SLACK_TOKEN``.

In case you need private channels as part of the list, you have to
specify the channel ID::

  {
    "notify": {
      "slack": {
        "accred.one": ["#alert_channel_alpha", "11223344"],
      }
    }
  }

Channel ID ``11223344`` can be obtained quickly from the URL to a
message of the target private channel. Of course, the Slack App needs
to be part of the private channel.

PagerDuty
---------

This configurable notifier will send alerts to PagerDuty.
The following is an example configuration for this notifier
to be added to a configuration file and used with the ``pagerduty``
option when executing your compliance checks.

Note that you have two options to configure the PagerDuty notifier:

* Provide a list of checks by class path within an accreditation. This allows you
  to define which checks within the accreditation will trigger PageDuty notifications::

    {
      "pagerduty": {
        "my.accred1": {
          "service_id": "SERVICE_ID",
          "checks": [
            "package.category.checks.test_module_one.CheckClassOne",
            "package.category.checks.test_module_two.CheckClassTwo"
          ]
        }
      }
    }

* Provide accreditations only and the notifier will send alerts for all checks with those
  accreditations::

    {
      "pagerduty": {
        "my.accred1": "SERVICE_ID"
      }
    }

Note that the ``service_id`` field is the service id from PagerDuty, e.g. ``PABC123``.
The PagerDuty notifier loads the active incidents to determine if
it needs to create a new incident or update an existing one by using the ``service_id``.
To get your service ID, go to your service in the PagerDuty dashboard and the
service ID will be the last path element (7 characters) of the URL.  For example
for ``https://my-service/PABC123``, the service ID is ``PABC123``.

This notifier also needs to know the credentials for sending message to PagerDuty.
Include the following in your credentials file::

  [pagerduty]
  events_integration_key=XXX

GitHub Issue
------------

Depending on the configuration this notifier will create or update a GitHub
issue per check or as a summary issue per accreditation. If an open issue
already exists then the notification will be added to the existing issue as
an issue comment otherwise a new issue will be created.

This notifier needs to know the credentials for interacting with the provided
GitHub repositories.  Your credentials should, at a minimum, have
``write`` access to all repositories specified for notifications to function
correctly. Provide your GitHub id and personal access token in your
credentials file as shown below::

  [github]
  username=my-gh-id
  token=my-gh-personal-access-token

GH Summary Issue by Accreditation
*********************************

A configuration element for each accreditation is necessary to send summary
issue notifications using this notifier. Summary notifications send all
result statuses for checks within the accreditation.  Each accreditation
configuration should consist of a list of repositories to send the notifications
to, optionally a project and column to assign your notification to, along
with a "summary_issue" sub-document dictionary that is used by the notifier to
configure the summary issue.  To specify a repository provide the GitHub
"owner" and "repository" in the form of ``owner/repository``. The "summary_issue"
can be configured with the following fields:

- "title"
   - Required
   - Provides the title of the issue
- "frequency"
   - Optional
   - Valid values are
      - "day"
         - Prepends the title with ``<YYYY-MM-DD> -``
         - ``<YYYY-MM-DD>`` label is added
      - "week"
         - Prepends the title with ``<year>, <iso week>W -``
         - ``<year>`` label is added
         - ``<iso week>W`` is added
      - "month"
         - Prepends the title with ``<year>, <month>M -``
         - ``<year>`` label is added
         - ``<month>M`` is added
      - "year"
         - Prepends the title with ``<year> -``
         - ``<year>`` label is added
- "labels"
   - Optional
   - List of strings
   - Tags the issue with the provided list of labels
- "message"
   - Optional
   - List of strings
   - Provides an overview of the issue to be included in the issue body
     upon creation
- "assignees"
   - Optional
   - List of strings (GH user IDs)
   - Assigns the issue to the list of users
- "rotation"
   - Optional
   - List of lists of strings (GH user IDs)
   - The "frequency" is required when setting a rotation
   - When present with "frequency", overrides the "assignees" setting
   - Assigns the issue to the list of users based on the frequency and order
     in the rotation list of lists

The following is an example configuration for this notifier to be added to a
configuration file and used with the ``-C`` option when executing your
compliance checks::

  {
    "notify": {
      "gh_issues": {
        "accr1": {
          "repo": ["my-org/accr1-repo"],
          "project": {"Super cool project": "Triage"},
          "summary_issue": {
            "title": "Super cool summary issue for accr1",
            "frequency": "week",
            "message": [
              "This is line one.",
              "This is line two."
            ],
            "rotation": [["moe", "larry", "curly"], ["foo", "bar"]],
            "assignees": ["the-dude", "walter", "donnie"]
          }
        },
        ...
      }
    }
  }

GH Issue Per Check
******************

A configuration element for each accreditation is necessary to send
notifications per check using this notifier.  Each accreditation configuration
should consist of a list of repositories to send the notifications to, a
list of check execution statuses to send notifications for, and optionally a
list of projects boards and project columns to add the notification issues to.
To specify a repository provide the GitHub "owner" and "repository"
in the form of ``owner/repository``.  Valid status values include "pass",
"warn", "fail", and "error".  If no status configuration is provided then the
"fail" status is used as the default.  You can also optionally limit your
notifications to a set of checks within an accreditation by providing a list
of check paths with a "checks" list. Finally to specify project boards to
assign issues to, set "project" to a dictionary where the keys are project
names and the values are the column names.  The following is an example
configuration for this notifier to be added to a configuration file and
used with the ``-C`` option when executing your compliance checks::

  {
    "notify": {
      "gh_issues": {
        "accr1": {
          "repo": ["my-org/accr1-repo"],
          "project": {"Super cool project": "Triage"},
          "status": ["fail", "error"]
        },
        "accr2": {
          "repo": ["my-org/accr2-repo"],
          "project": {"Some other super cool project": "Backlog"},
          "status": ["error"],
          "checks": [
            "chk_pkg.chk_cat_foo.checks.chk_module_foo.FooCheckClass",
            "chk_pkg.chk_cat_foo.checks.chk_module_bar.BarCheckClass"
          ]
        }
      }
    }
  }

Evidence Locker
---------------

This notifier will take your check execution for all accreditations and put
a summary markdown file ``notifications/alerts_summary.md`` into your evidence
locker.  The summary markdown file will **only** be pushed to the remote
evidence locker if the ``full-remote`` argument is applied to the ``evidence``
option when executing your checks otherwise the file will remain in the local
evidence locker.  No additional configuration is required for this notifier.

Security Advisor Findings
-------------------------

This configurable notifier will post findings to Security Advisor Findings API
per accreditation. The following is an example configuration for this notifier
to be added to a configuration file and used with the ``-C`` option when
executing your compliance checks::

  {
    "notify": {
      "findings": {
        "accr1": "https://us-south.secadvisor.cloud.ibm.com/findings",
        "accr2": "https://eu-gb.secadvisor.cloud.ibm.com/findings"
      }
    }
  }

Supported regions for Security Advisor Findings API
  - us-south: https://us-south.secadvisor.cloud.ibm.com/findings
  - eu-gb: https://eu-gb.secadvisor.cloud.ibm.com/findings

This notifier also needs to know the credentials for sending findings
to Security Advisor Findings API. Include the following in your credentials
file::

  [findings]
  api_key=platform-api-key

``api_key`` is your IBM Cloud Platform API Key.
