.. -*- mode:rst; coding:utf-8 -*-

compliance-tool's documentation
===============================

Tool to run compliance control checks as unit tests.

`#compliance-tooling <https://ibm-cloudplatform.slack.com/messages/C3X0P7CUB>`_

Installation
------------

For users
~~~~~~~~~

You can use the following ``pip`` command for installing
``compliance-tool`` in your environment. The URL is also suitable for
``requirements.txt`` and ``setup.py`` (using ``setuptools``)::

  $ pip install git+ssh://git@github.ibm.com/clouddataservices/compliance-tool.git#egg=compliance-tool


You can specify a specific version. For example ``v0.0.1``::

  $ pip install git+ssh://git@github.ibm.com/clouddataservices/compliance-tool.git@v0.0.1#egg=compliance-tool

See the :ref:`quick-start` section for a brief introduction to the
tool usage. Also, see :ref:`running-on-travis` section for getting
information about how to automate the execution in Travis.

For developers
~~~~~~~~~~~~~~

.. code-block:: bash

   $ git clone git@github.ibm.com:cloumpose/compliance-tool
   $ cd compliance-tool
   $ git submodule update --init --recursive
   $ virtualenv --no-site-packages venv
   $ . venv/bin/activate
   $ make develop

Guides
------

.. toctree::
   :maxdepth: 1

   quick-start
   design-principles
   oscal
   evidence-partitioning
   fixers
   report-builder
   notifiers
   coding-standards
   running-on-travis
   running-on-tekton

Source code
-----------

.. toctree::
   :maxdepth: 2

   modules
