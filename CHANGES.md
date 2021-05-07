# [1.19.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.19.0)

- [ADDED] Pre-commit hook for running `bandit` as part of CI/CD was added.
- [CHANGED] Replaced the deprecated `imp` library with `importlib`.
- [CHANGED] Replaced the deprecated `ibm_security_advisor_findings_api_sdk` library with `ibm_cloud_security_advisor`.
- [FIXED] Added clarifying PagerDuty notifier documentation content.
- [FIXED] Addressed `bandit` (minor) security issue findings.

# [1.18.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.18.0)

- [CHANGED] Now using `pathlib` exclusively for operating system filepath and file functionality.
- [FIXED] README table of contents generation multi-blank line bug is resolved.

# [1.17.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.17.0)

- [ADDED] Locker get_large_files method added to return large files in the locker.
- [ADDED] Logging of large files added to remote push operation.

# [1.16.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.16.0)

- [ADDED] Locker get_empty_evidences method added to return all empty evidence paths.
- [ADDED] Evidence base class has override-able is_empty property.

# [1.15.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.15.0)

- [FIXED] The evidences context manager now raises an exception when no evidence is found.

# [1.14.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.14.0)

- [ADDED] The `filtered_content` attribute has been added to `RawEvidence`.
- [ADDED] Locker clone duration logging has been added.
- [FIXED] The `binary_content` attribute on raw evidence is retained as metadata now.
- [FIXED] All partitioned evidence defined via constructor correctly retains attributes now.

# [1.13.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.13.0)

- [ADDED] Configurable shallow cloning of locker is now supported.

# [1.12.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.12.0)

- [ADDED] Referencing historical evidence from a previous locker is now supported.
- [ADDED] The optional `locker.prev_repo_url` configuration element was added.
- [ADDED] Evidence used by checks found in reports metadata includes the locker URL field now.
- [ADDED] Links to evidence used by checks found in the table of contents point to the appropriate lockers.
- [ADDED] Evidence used by checks found in check_results.json includes the locker URL field now.

# [1.11.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.11.0)

- [ADDED] Fetcher execution using `--evidence full-remote` mode pushes to remote locker now.

# [1.10.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.10.1)

- [FIXED] Reading raw evidence in checks is now supported.
- [FIXED] Cleaned up Design Principles document formatting.
- [FIXED] Virtual environment creation syntax corrected in Quick Start document.
- [ADDED] Binary content fetcher and checks included in demo examples.

# [1.10.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.10.0)

- [CHANGED] GitHub Issues notifier can create issues for a subset of an accreditation's checks with a new configuration element.

# [1.9.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.9.1)

- [FIXED] Github service `Github.get_issue_comments` returns all issue comments now.

# [1.9.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.9.0)

- [ADDED] Storing raw evidence as binary content is now possible.

# [1.8.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.8.1)

- [CHANGED] Improved selective fetcher bulk execution performance.

# [1.8.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.8.0)

- [ADDED] Selective fetcher bulk `--include` and `--exclude` execution is now possible.

# [1.7.2](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.7.2)

- [FIXED] LazyLoader namedtuple defaults removed; Framework compatible with Python 3.6 again.

# [1.7.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.7.1)

- [FIXED] Subclassed evidence support works with cached evidence now.

# [1.7.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.7.0)

- [ADDED] Check evidence decorators and context manager now support subclassed evidence.
- [ADDED] Evidence objects now have a content_as_json property.

# [1.6.5](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.5)

- [ADDED] Direct calls to the GH API can be made using the Github service now.

# [1.6.4](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.4)

- [ADDED] Demo set of fetchers and checks added.
- [ADDED] "Try It" section added to the README.
- [CHANGED] Quick Start guide updated to include references to demo fetchers and checks implementation.

# [1.6.3](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.3)

- [ADDED] Fetcher and check execution times are now included in execution logging.

# [1.6.2](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.2)

- [FIXED] Table of contents now handled appropriately for locker without a README.

# [1.6.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.1)

- [FIXED] Table of contents now handles old/abandoned report evidence metadata appropriately.

# [1.6.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.6.0)

- [ADDED] Check reports table of contents now appended to an evidence locker's README.
- [ADDED] `ComplianceCheck.get_historical_evidence` supports historical evidence retrieval.

# [1.5.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.5.0)

- [ADDED] Remote locker push failure notifications were added.
- [ADDED] Logging for git locker operations was added.
- [ADDED] Notifier logging was added.
- [CHANGED] The file descriptor (stdout) notifier always notifies now.

# [1.4.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.4.0)

- [CHANGED] PagerDuty notifier can send alerts for a subset of the accreditation checks based on the config.
- [ADDED] A warning for possible sensitive information contained within notifications was added.

# [1.3.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.3.0)

- [CHANGED] Simplified `controls.json` format.  Original format is also supported.
- [ADDED] Documentation for `controls.json` and check execution was added.
- [ADDED] ControlDescriptor unit tests were added.
- [FIXED] ComplianceFetcher session object is auto-closed now in tearDownClass.

# [1.2.7](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.7)

- [CHANGED] Removed PyYAML dependency to resolve downstream dependency issues.
- [CHANGED] Removed Github.get_issue_template helper method.

# [1.2.6](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.6)

- [FIXED] ComplianceFetcher.session can now be reset.

# [1.2.5](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.5)

- [FIXED] Credentials section bug affecting the Slack notifier is squashed.

# [1.2.4](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.4)

- [CHANGED] Fetchers and checks that failed to load appear as errors in STDERR now.

# [1.2.3](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.3)

- [CHANGED] Github service `get_commit_details` now take `path` as an optional argument.

# [1.2.2](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.2)

- [FIXED] Github service branch protection method now returns "required_signatures" content.

# [1.2.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.1)

- [FIXED] Notifier `msg_` methods are now accurately found based on check `test_` method names.

# [1.2.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.2.0)

- [ADDED] Branch option to retrieving commit details from the Github service was added.

# [1.1.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.1.0)

- [ADDED] Repository details retrieval was added to Github service class.
- [ADDED] Recent commit details retrieval was added to Github service class.
- [ADDED] Repository branch protection details retrieval was added to Github service class.

# [1.0.2](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.0.2)

- [FIXED] Added PyYAML library as a dependency to resolve Github service issue.

# [1.0.1](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.0.1)

- [FIXED] Added external evidence as a valid evidence type to evidence map.

# [1.0.0](https://github.com/ComplianceAsCode/auditree-framework/releases/tag/v1.0.0)

- [ADDED] Made the Auditree Framework public.
