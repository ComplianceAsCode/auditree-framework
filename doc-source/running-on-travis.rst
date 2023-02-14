.. -*- mode:rst; coding:utf-8 -*-

.. _running-on-travis:

Running on Travis
=================

Running the Auditree framework from a CI like Travis can be really useful for
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

* A git repository for storing generated evidence. You should create a
  private project/org for this.

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



Travis artifacts
----------------

This is a typical `.travis.yml` file:

.. code-block:: yaml

   language: python
   python:
     - "3.7"
   install:
     - pip install -r requirements.txt
   script:
     - make clean
     - ./travis/run.sh

Basically, this will firstly install the dependencies through
``pip install -r requirements.txt`` and then generate the credentials file from
using Travis environment variables.

Credentials
~~~~~~~~~~~

The recommended way to use credentials in a CI job is to export them as environment variables.
Auditree will automatically parsed the environment variables available to the process and make them available to the fetchers if they follow a specific structure.

For more information on how to do this, have a look to the :ref:`credentials` section.


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
       "repo_url": "https://github.com/my-org/my-evidence-repo"
     },
     "notify": {
       "slack": {
         "demo.hipaa": ["#security-team", "#hipaa-compliance"],
         "demo.soc2": ["#soc2-compliance", "#operations"]
       }
     }
   }
