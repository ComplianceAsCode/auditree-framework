.. -*- mode:rst; coding:utf-8 -*-

.. _quick-start:

Quick Start
===========

If any terminology used in this quick start guide is unclear, have a look at the
:ref:`design-principles` documentation for clarification.

The Auditree framework requires at least one directory containing fetchers and
checks.  Let's use the fetchers and checks packaged up in the ``demo`` folder
of the ``auditree-framework`` project as an example.  First things first, we need
to ensure that we have a proper Python virtual environment configured and running::

  $ cd demo
  $ python -m venv venv
  $ . ./venv/bin/activate
  $ pip install -r requirements.txt

A typical execution consists of two phases:

* Running the fetchers::

    $ compliance --fetch --evidence local -C auditree_demo.json -v

  Running this command generates a Git repository locally at ``/$TMPDIR/compliance``
  and it executes all fetchers found within the ``demo_example`` package.

* Running the checks::

    $ compliance --check demo.arboretum.accred,demo.custom.accred --evidence local -C auditree_demo.json -v

  Running this command executes checks associated with the specified accreditations,
  creates check result reports in the evidence locker, executes notifiers (you can
  see the messages in the output), updates the evidence locker README with a check
  report table of contents and generates a file in the evidence locker root called
  ``check_results.json`` with detailed information about the check execution.

Advanced Topics
---------------

Configuration
~~~~~~~~~~~~~

There are two configuration files used to configure the execution of the
``auditree-framework``.  The main configuration file can be named anything you
like.  In the case of our demo we've chosen the name ``auditree-demo.json``.  There
is also a check to accreditation mapping configuration file and this file must be
named ``controls.json``.

controls.json
~~~~~~~~~~~~~

The mapping between a check (check class path) and accreditations
(a list of accreditations) happens in the ``controls.json`` configuration
file.  Each new check must be included in ``controls.json`` in
order to be considered for execution by the Auditree framework.
Note that this is not the case for fetchers, where all are executed.
As an example, the format for ``controls.json`` is as follows::

  {
    "chk_pkg.chk_cat_foo.checks.chk_module_foo.FooCheckClass": ["accred.one"],
    "chk_pkg.chk_cat_bar.checks.chk_module_bar.BarCheckClass": ["accred.one", "accred.two"]
  }

Agents
~~~~~~

All fetchers can be executed in "agent" mode. Agents will cryptographically sign
any evidence they fetch. The agent name, evidence digest and signature can be
found in the ``index.json`` metadata file. See :ref:`verifying-signed-evidence`
for instructions on how to manually verify signatures.

To configure an agent, add the following to your main configuration::

  {
    "agent_name": "my-agent-name",
    "agent_private_key": "/path/to/key.pem",
    ...
  }

Each agent must have a unique name. By default, any evidence created by an agent
will be stored under the corresponding agent directory (e.g.
``agents/my-agent-name/raw/system/uptime.txt``). You can set
``"use_agent_dir": false`` to suppress this behavior.

Signed evidence can be used in checks. It is automatically verified when it's
loaded from the locker. The public key used to verify the evidence must be made
available in the locker under ``raw/auditree/agent_public_keys.json``. This is a
special evidence and must take the following form::

  {
    "my-agent-name": "-----BEGIN PUBLIC KEY-----\n...",
    "my-other-agent-name": "-----BEGIN PUBLIC KEY-----\n...",
    ...
  }

We recommend you implement an additional fetcher to pull this public keys
evidence into the locker and ensure it's kept up-to-date. You can sign this
evidence too using an agent configured with ``"use_agent_dir": false``. However,
it means only that agent can then be used to execute checks against any signed
evidence.

Remote Evidence Locker
~~~~~~~~~~~~~~~~~~~~~~

Storing and using evidence in a Git remote hosting service repository is achievable
by using the ``--evidence`` option with settings of either ``no-push`` or
``full-remote`` along with the locker configuration URL similar to the one found
in the ``auditree_demo.json``.  Set the locker URL to the URL of your remote
evidence locker repository and use ``--evidence no-push`` to pull down a remote
evidence locker only or ``--evidence full-remote`` to pull down and push to a
remote evidence locker.  Finally you'll need to configure your credentials file
with the appropriate personal access token for your Git remote hosting service.  The
credentials file defaults to ``~/.credentials`` or use the ``--creds-path`` option
to point elsewhere.  Valid section headings for Git remote hosting services in your
credentials are ``github``, ``github_enterprise``, ``bitbucket``, and ``gitlab``.
Using ``github`` as an example, add the following to your credentials file::

  [github]
  token=XXX

Once the credentials are set up, you can run fetchers and checks in ``no-push``
or ``full-remote`` mode.

For a fetcher execution the Auditree framework will ``pull`` the repository to
``/$TMPDIR/compliance`` (only if it does not exist already), and then run all
of the fetchers.  If evidence time to live (TTL) has not expired for a given
evidence file then the associated fetcher will perform a no-op run.

It is important to note that when using the ``no-push`` option, your evidence
locker will not be pushed to the remote evidence locker at the end of your fetcher
execution.  This is handy for testing the current state of the evidence in your
evidence locker::

  $ compliance --fetch --evidence no-push -C auditree_demo.json

However using the ``full-remote`` option will push your evidence locker to the
remote locker::

  $ compliance --fetch --evidence full-remote -C auditree_demo.json

Likewise once the credentials are set up and you've executed your fetchers in
either ``no-push`` or ``full-remote`` mode you can now execute your checks in
``no-push`` mode which will not push the evidence locker to the remote evidence
locker::

  $ compliance --check demo.arboretum.accred,demo.custom.accred --evidence no-push -C auditree_demo.json


However using the ``full-remote`` option will push your evidence locker to the
remote locker::

  $ compliance --check demo.arboretum.accred,demo.custom.accred --evidence full-remote -C auditree_demo.json

Notifications
~~~~~~~~~~~~~

You can also configure the check run to send notifications to Slack,
GitHub (as issues), PagerDuty, the evidence locker, Findings, and the terminal
console which is the default.  To do this add the desired notifier(s) to your
configuration file similar to ``auditree_demo.json`` and use the ``--notify``
option as part of the check execution.  For example, you can use the
``slack`` notifier to send Slack alerts::

  $ compliance --check demo.custom.accred --evidence no-push -C auditree_demo.json --notify slack

This will run only ``demo.custom.accred`` accreditation in ``no-push`` mode and
Slack notifications for this accreditation will be sent to the channels and
individuals specified in your configuration.  In addition to configuring the
notifiers, notifier specific credentials also need to be added to your credentials
file.  For example, for Slack you can either provide a webhook or a token::

  [slack]
  webhook=XXX

Slack webhooks cannot be used for posting messages into private channels. If you
need this, we recommend to use a Slack app token instead::

  [slack]
  token=XXX

Each notifier requires its own configuration and credentials and you can specify
as many notifiers as you want on any given check execution.

Recommendations
---------------

* Use the example project showcased above as a template for your configuration/execution
repository/project:

  * Put your ``fetchers`` and ``checks`` in separate folders. Technically, there
    is no rule about fetcher and check organization, but it is a good guideline to
    follow.  As you add more fetchers and checks you can create more sub-directories.

  * Create a ``templates`` folder for your check report templates.  Remember that
    they should have the same path as your report evidence.

  * Execute fetchers and checks separately.

* When debugging, always use the safest options for the Auditree framework. This
  should mitigate unintended slack notifications or commits to your remote evidence
  locker.

  * It doesn't hurt to delete your local evidence locker ``compliance`` folder.
    This ensures a clean execution and should mirror an official run from a CI
    tool.

  * Notify using the ``stdout`` notifier which is the default.

  * Only use ``--evidence local`` or ``evidence no-push`` options.
