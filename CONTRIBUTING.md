# Contributing

If you want to add to the framework, please familiarise yourself with the code & our [Coding Standards][]. Make a fork of the repository & file a Pull Request from your fork with the changes. You will need to click the checkbox in the template to show you agree to the [Developer Certificate of Origin](../blob/master/DCO1.1.txt).

If you make **regular & substantial contributions** to Auditree, you may want to become a collaborator. This means you can approve pull requests (though not your own) & create releases of the tool. Please [file an issue][new collab] to request collaborator access. A collaborator supports the project, ensuring coding standards are met & best practices are followed in contributed code, cutting & documenting releases, promoting the project etc.

## Fetchers & checks

If you would like to contribute checks, either add them via PR to[Arboretum][] or push to your own repository & let us know of its existence.

There are some guidelines to follow when making a common fetcher or check:

- Be sure to leverage the configuration JSON file used at runtime by the compliance-tool.

  - The sub-document structure to adhere to for a common module is one where the root of the sub-document is the org. Under the org there should be a name field which would refer to the organization’s name. Each common module configuration sub-document should also be under the org sub-document. For example:

```
        {
           ...
           "org": {
             "name": "my-org-name",
             "check-and-fetch-baz": { ... },
             "check-foo": { ... },
             "fetch-bar": { ... },
             ...
           },
           ...
        }
```

- If you need to sub-class a basic evidence type (raw, derived, report) in order to provide helper methods that handle the evidence content, be sure not to use a decorator to reference that evidence. Instead use the compliance tool evidence module get_evidence_by_path function.

- Additionally when dealing with any evidence in a common fetcher or check it would be best to use the compliance tool evidence module get_evidence_by_path function rather than adding the evidence to the evidence cache directly.

- Be sure to provide a report template as this will be included in the common-compliance package and used for your common check(s).

- Be sure to provide notifier methods that correspond to your checks when appropriate.

- Happy coding.


## Code formatting and style

Please ensure all code contributions are formatted by `yapf` and pass all `flake8` linter requirements.
CI/CD will run `yapf` and `flake8` on all new commits and reject changes if there are failures.  If you
run `make develop` to setup and maintain your virtual environment then `yapf` and `flake8` will be executed
automatically as part of all git commits.  If you'd like to run things manually you can do so locally by using:

```shell
make code-format
make code-lint
```

## Testing

Please ensure all code contributions are covered by appropriate unit tests and that all tests run cleanly.
CI/CD will run tests on all new commits and reject changes if there are failures. You should run the test
suite locally by using:

```shell
make test
```

[Arboretum]: https://github.com/ComplianceAsCode/auditree-arboretum
[Coding Standards]: https://github.com/ComplianceAsCode/auditree-framework/blob/master/doc/coding-standards.rst
[flake8]: https://gitlab.com/pycqa/flake8
[new collab]: https://github.com/ComplianceAsCode/auditree-framework/issues/new?template=new-collaborator.md
[yapf]: https://github.com/google/yapf
