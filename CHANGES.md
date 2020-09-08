# 1.4.0 (2020-09-03)

- [CHANGED] PagerDuty notifier can send alerts for a subset of the accreditation checks based on the config.
- [ADDED] A warning for possible sensitive information contained within notifications was added.

# 1.3.0 (2020-09-01)

- [CHANGED] Simplified `controls.json` format.  Original format is also supported.
- [ADDED] Documentation for `controls.json` and check execution was added.
- [ADDED] ControlDescriptor unit tests were added.
- [FIXED] ComplianceFetcher session object is auto-closed now in tearDownClass.

# 1.2.7 (2020-08-28)

- [CHANGED] Removed PyYAML dependency to resolve downstream dependency issues.
- [CHANGED] Removed Github.get_issue_template helper method.

# 1.2.6 (2020-08-28)

- [FIXED] ComplianceFetcher.session can now be reset.

# 1.2.5 (2020-08-26)

- [FIXED] Credentials section bug affecting the Slack notifier is squashed.

# 1.2.4 (2020-08-24)

- [CHANGED] Fetchers and checks that failed to load appear as errors in STDERR now.

# 1.2.3 (2020-08-18)

- [CHANGED] Github service `get_commit_details` now take `path` as an optional argument.

# 1.2.2 (2020-08-14)

- [FIXED] Github service branch protection method now returns "required_signatures" content.

# 1.2.1 (2020-08-12)

- [FIXED] Notifier `msg_` methods are now accurately found based on check `test_` method names.

# 1.2.0 (2020-08-11)

- [ADDED] Branch option to retrieving commit details from the Github service was added.

# 1.1.0 (2020-08-11)

- [ADDED] Repository details retrieval was added to Github service class.
- [ADDED] Recent commit details retrieval was added to Github service class.
- [ADDED] Repository branch protection details retrieval was added to Github service class.

# 1.0.2 (2020-07-28)

- [FIXED] Added PyYAML library as a dependency to resolve Github service issue.

# 1.0.1 (2020-07-27)

- [FIXED] Added external evidence as a valid evidence type to evidence map.

# 1.0.0 (2020-07-21)

- [ADDED] Made the Auditree Framework public.
