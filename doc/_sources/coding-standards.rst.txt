.. -*- mode:rst; coding:utf-8 -*-

.. _coding-standards:

Coding Standards
----------------

In this project, we use Python as programming language so please
follow these rules:

* Keep the code tidy using `flake8
  <http://flake8.pycqa.org/en/latest>`_. Don't introduce new
  violations and remove them if you spot any. This is enforced now by
  travis build. To check your code locally, use:
  
  ```
  make lint
  ```

* Please provide good unit tests for your code changes. It is
  important to keep a good level of test coverage.

* Document everything you create using docstring within the code. We
  use `sphinx <http://www.sphinx-doc.org>`_ for documentation.

* Test your code locally and make sure it works before creating a PR.

  ```
  make unit-tests-with-coverage
  ```


Avoid code smells
~~~~~~~~~~~~~~~~~

* `An interested reading
  <https://sourcemaking.com/refactoring/smells>`_

* Your change makes the tool to run slower. Ask yourself if actually
  that's the only way to do it (or somebody for advice).

* Unit tests must be fast (really fast) and never use network
  resources.

* Do not use shell commands (`os.system`, `subprocess`, etc.) unless
  the usage would save us from days/tons of work. Python libraries are
  preferred in most cases and if there is not a Python library for it,
  then explain your case and try to convince people why it is better
  using a shell command.

Avoid third-party stuff
~~~~~~~~~~~~~~~~~~~~~~~

* Third-party libraries: using third-party libraries is not always a
  good idea. While they can be beneficial, using third-party libraries
  means we must maintain the code to be compatible with them and the
  installation process gets more complicated. So, by default, try to use
  Python built-ins. If you actually need to introduce a new third-party
  library, please explain your reasoning and get a +1 from somebody else
  for it.

* Third-party programs: due the reasons above, avoid using external programs as
  much as possible and get consensus if you need to introduce one.

Always Test
~~~~~~~~~~~

* Always test your code, please dont assume it works. To do this, add
  unit tests and pay attention to the coverage results that come back.
  
  ```
  make unit-tests-with-coverage
  ```

* Always make sure that the entire test suite runs cleanly
