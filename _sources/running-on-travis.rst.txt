.. -*- mode:rst; coding:utf-8 -*-

.. _running-on-travis:

Running on Travis
=================

Running compliance tool from a CI like Travis can be really useful for
executing your compliance checks periodically. Thus you can track the
current level of compliance for different standards and also notify
people whenever there is a failure, so it can be fixed in some way.

This can be done in many different ways, so you don't have to follow
this guide if it does not fit your requirements. However, it always
useful to know what it is required so you can adapt this guide to your
needs.


Basically, this will what you will need:

* A ``.travis.yml``: this will define the Travis run which will run
  ``travis/run.sh`` script.

* A git repository for storing generated evidence. You can create a
  private GHE project for this.

* Credentials generator: for that, a python script can be used for
  generating the credentials files from environment variables defined
  in Travis.

* Results storage: check results are stored to the evidence locker as
  ``check_results.json``.

Bare in mind that a compliance check project is a bit tricky to
configure since you will be pushing new code there and also running
**official** compliance executions. You can resolve this issue by
having 2 Git repositories: one for check development with a
development Travis configuration and another one just for cloning it
and run ``compliance`` with official parameters.

However, this can be done in the same repository noting that there are
`development` runs (they will not notify nor push any evidence to the
evidence collector repository) and `official` runs (which will send
notifications and push evidences to Git).

You can have a look into `Cloudant Compliance Checks
<https://github.ibm.com/cloumpose/cloudant-compliance-checks>`_
to get more details about what it is explained here.



Travis artifacts
----------------

This is a typical `.travis.yml` file:

.. code-block:: yaml

   language: python
   python:
     - "2.7"
   group: bluezone  # if it needs to be run within IBM VPN
   install:
     - pip -r requirements.txt
     - ./travis/gen-credentials.py > ~/.credentials
   script:
     - make clean
     - ./travis/run.sh
   after_script:
     - rm  ~/.credentials

Basically, this will firstly install the dependencies through ``pip -r
requirements.txt`` and then generate the credentials file from using
Travis environment variables.

Credentials generation
~~~~~~~~~~~~~~~~~~~~~~

This is an implementation you might want to use for your project of
``gen-credentials.py``:

.. code-block:: python

   #!/usr/bin/env python
   # -*- coding:utf-8; mode:python -*-

   '''This script generates a config file suitable to be used by
   `utilitarian.credentials.Config` from envvars. This is useful for
   Travis CI that allows to deploy credentials safely using envvars.

   Any new supported credential must be added to SUPPORTED_SECTIONS which
   includes a list of sections of `Config` supported by the script. For
   example, adding 'github' will make the script to generate
   `github.username` from GITHUB_USERNAME and `github.password` from
   GITHUB_PASSWORD, if both envvars are defined.
   '''

   import os
   import sys
   import ConfigParser


   SUPPORTED_SECTIONS = ['github_enterprise', 'slack']


   def main():
       matched_keys = filter(
           lambda k: any([k.lower().startswith(x) for x in SUPPORTED_SECTIONS]),
           os.environ.keys()
       )
       if not matched_keys:
           return 0

       cfg_parser = ConfigParser.ConfigParser()
       for k in matched_keys:
           # split the section name and option from this env var (max()
           # to ensure the longest match)
           section = max(
               [s for s in SUPPORTED_SECTIONS if k.lower().startswith(s)],
               key=len
           )
           option = k.split(section.upper())[1][1:].lower()

           # add to the config
           if not cfg_parser.has_section(section):
               cfg_parser.add_section(section)
           cfg_parser.set(section, option, os.environ[k])

       cfg_parser.write(sys.stdout)

       return 0


   if __name__ == '__main__':
       exit(main())

So, for instance, using the previous script you will be able to create
the credentials required for ``github_enterprise`` and ``slack`` by
defining the following environment variables in Travis:

* ``GITHUB_ENTERPRISE_TOKEN = XXX``

* ``SLACK_WEBHOOK = YYY``

Using those variables, ``./travis/gen-credentials.py >
~/.credentials`` will generate::

  [github_enterprise]
  token=XXX

  [slack]
  webhook=YYY

This method has a few limitation:

* Do not use ``$`` as part of the value of any variable as they will
  be evaluated by bash.

* You will need to add a new service into the
  ``SUPPORTED_SECTIONS``. This is actually good since a manual
  addition requires a code change (so new credentials are
  tracked).

``travis/run.sh``
~~~~~~~~~~~~~~~~~

Travis will call this script in two different ways:

* As part of a change in the repo, so it would be considered a
  development run.

* A call through Travis API, made by a cron job (or a robot)
  periodically. This will be considered the `official` run.

This is an example of a ``travis/run.sh`` file:

.. code-block:: bash

   #!/bin/bash

   NON_OFFICIAL="--evidence no-push --notify stdout"
   OFFICIAL="--evidence full-remote --notify slack"

   # is this an official run or not?
   if [ "$TRAVIS_BRANCH" == "master" ] && [ -z $TRAVIS_COMMIT_RANGE ]; then
     # this is official as it has been run by an external call
     # GHE does not support cron jobs yet, so this hack is needed.
     OPTIONS="$OFFICIAL"
   else
     OPTIONS="$NON_OFFICIAL"
   fi

   # run fetchers
   compliance --fetch $OPTIONS -C official.json

   # run checks
   compliance --check $ACCREDITATIONS $OPTIONS -C official.json
   retval=$?

   exit $retval

Note that the arguments used in the ``compliance`` invocation depend
on whether this is an official run or not. This script assumes you
have stored the official configuration into ``official.json`` file:

.. code-block:: json

   {
     "locker": {
       "repo_url": "https://github.ibm.com/YOUR-ORG/evidence-collector"
     },
     "notify": {
       "slack": {
         "demo.hipaa": ["#security-team", "#hipaa-compliance"],
         "demo.soc2": ["#soc2-compliance", "#operations"]
       }
     }
   }
