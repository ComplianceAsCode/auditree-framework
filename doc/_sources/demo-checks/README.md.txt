# Demo repo for compliance-tool

This is an example of a repository layout that could be use with the
compliance. This repository may contain fetchs and/or checks and for
running them you should:

```
$ git clone git@github.ibm.com:cloumpose/compliance-tool.git
$ cd compliance-tool
$ mkvirtual env
$ . ./env/bin/activate
$ pip install -r doc/demo-checks/requirements.txt
$ compliance --fetch doc/demo-checks
$ compliance --check 'demo.accreditation1,demo.accreditation2' doc/demo-checks
```

## Fetchers and checks directory

It contains both fetchers and checks and they could be structured in
any way that fits your requirements. In this example, `demo` is the
directory containing a few examples. You can substitute `demo` by any
other meaningful name as your organization/unit name.

### `evidence` module

Within `demo`, you must provide a module called `evidence`. This can
be a simple `evidence.py` file or, as in this example, can be a
directory `evidence` with an `__init__.py`. In both cases, you have to
make sure that you add your evidence objects using:

```
from compliance.config import get_config

get_config().add_evidences([YOUR_KNOWN_EVIDENCES])
```

The compliance runner will collect all these evidences and check that
there is not conflicts between different repositories. Note that you
can provide `concrete_evidences.py` to provide helpful functionality
for concrete RawEvidences.

## controls.json

This is definition of what check provides what functionality to a
given accreditation control. This information is not fully used yet by
the compliance-tool but it is required for knowning what tests should
be included per accreditation. Note that this file will be merge with
any other provided (and compliance runner will check for clashes).

This file **must** be in the toplevel directory.

## setup.json

Configuration values that will affect to all fetchers and checkers of
this repository. In the future, we might support per-accreditation
level. See compliance-tool documentation for more information about
command-line arguments.
