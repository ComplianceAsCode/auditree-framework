.. -*- mode:rst; coding:utf-8 -*-

Auditree framework documentation
================================

Tool to run compliance control checks as unit tests.

Installation
------------

For users
~~~~~~~~~

The framework is uploaded to `pypi <https://pypi.org/project/auditree-framework/>`_.
You can install it via:

.. code-block:: bash

   $ pip install auditree-framework

See the :ref:`quick-start` section for a brief introduction to the
tool usage. Also, see :ref:`running-on-travis` section for getting
information about how to automate the execution in Travis.

For developers
~~~~~~~~~~~~~~

.. code-block:: bash

   $ git clone git@github.com:ComplianceAsCode/auditree-framework.git
   $ cd auditree-framework
   $ python3 -m venv venv
   $ . venv/bin/activate
   $ make install && make develop

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
   verifying-signed-evidence

Source code
-----------

.. toctree::
   :maxdepth: 2

   modules
