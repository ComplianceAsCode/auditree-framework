.. -*- mode:rst; coding:utf-8 -*-

.. _report-builder:

Report Builder
==============

After tests have been run by the Auditree framework, the
:py:class:`~compliance.report.ReportBuilder` is executed in order to
render all the required reports. This is how it works:

1) Execution tree is passed to the ReportBuilder and it iterates over
   each ``ComplianceCheck`` object.

2) If the test object implements ``get_reports()``, then the method is
   called. If it is not implemented, it is assumed that the check is
   not required to create any reports.

3) If it is implemented, a list is expected with the following types
   of elements:

   * Evidence string paths, e.g. ``'reports/category1/evidence1.md'``
     or just ``'category1/evidence1.md'`` (``reports/`` will be
     appended automatically). In this case, ``ReportBuilder`` will
     look for a Jinja2 template at
     ``templates/category1/evidence1.md.tmpl`` and it will render and
     store into the locker. See :ref:`templating` section for more
     information.

     This is the recommended way of generating reports.

   * :py:class:`~compliance.evidence.ReportEvidence` object: the test
     creates them and should populate the content because
     ``ReportBuilder`` will expect the ``.content`` property to contain the
     content of the report to render.

     This method is not recommended as you will need to generate the
     content of the report within the check code, so there will be too
     many things there (format rendering, structure, etc.).

4) Report evidences are rendered and stored in the locker. If an error occurs
   during report generation, ``ReportBuilder`` will skip that repot and
   notify that the error occurred, in standard output. Note that report
   generation will not halt on an error, and will attempt to generate all other
   reports.


.. _templating:

Report templates
----------------

As above, reports can be generated using Jinja2_
report templates. When a path to report evidence is provided in a
ComplianceCheck object's ``get_reports`` method then the ``ReportBuilder`` will
attempt to locate a template matching the report evidence path provided.  For
example if the following is the path provided:

.. code-block:: python

   def get_reports():
       return ['reports/users/ssh.md']

The ``ReportBuilder`` will search for ``reports/users/ssh.md.tmpl`` in the
first ``templates`` directory that it can find. Typically the ``templates``
directory would be found at the same level as the ``checks`` and ``fetchers``
directories. For example::

  fetchers/
  checks/
  templates/
    reports/
      users/
        ssh.md.tmpl

The content of ``ssh.md.tmpl`` should be follow Jinja2 template syntax. The
following variables are available for use within the template:

* ``test``: the ComplianceCheck object.

* ``results``: a dictionary containing the statuses of the checks from the
  ``test`` object.

* ``all_failures``: a dictionary containing failures for each section/type.

* ``all_warnings``: a dictionary containing warnings for each section/type.

* ``evidence``: the ReportEvidence object.

* ``builder``: a reference to the ``ReportBuilder``.

* ``now``: a ``datetime`` object with the date at render time.

It is also possible to have a default template and if no template matching
the report evidence path/name provided by ``get_reports`` can be found,
``ReportBuilder`` will use the default template to generate the report
identified by the report evidence path/name.  Typically the default template
would live in the ``template`` directory as ``reports/default.md.tmpl``.


.. _Jinja2: http://jinja.pocoo.org/docs/latest/templates/
