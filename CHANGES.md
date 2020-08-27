# 1.4.0
 
- [IMPROVED] PagerDuty notifier can send alerts for a subset of the accreditation checks based on the config.
- [NEW] Added warning for possible sensitive information contained within notifications.

# 1.3.0

- [IMPROVED] Simplified `controls.json` format.  Original format is also supported.
- [NEW] Added documentation for `controls.json` and check execution.
- [NEW] Added ControlDescriptor unit tests.
- [FIXED] ComplianceFetcher session object is auto-closed now in tearDownClass.

# 1.2.7

- [CHANGED] Removed PyYAML dependency to resolve downstream dependency issues.
- [CHANGED] Removed Github.get_issue_template helper method.

# 1.2.6

- [FIXED] ComplianceFetcher.session can now be reset.

# 1.2.5

- [FIXED] Credentials section bug affecting the Slack notifier is squashed.

# 1.2.4

- [IMPROVED] Fetchers and checks that failed to load appear as errors in STDERR now.

# 1.2.3

- [IMPROVED] Github service `get_commit_details` now take `path` as an optional argument.

# 1.2.2

- [FIXED] Github service branch protection method now returns "required_signatures" content.

# 1.2.1

- [FIXED] Notifier `msg_` methods are now accurately found based on check `test_` method names.

# 1.2.0

- [NEW] Added branch option to retrieving commit details from the Github service.

# 1.1.0

- [NEW] Added repository details retrieval to Github service class.
- [NEW] Added recent commit details retrieval to Github service class.
- [NEW] Added repository branch protection details retrieval to Github service class.

# 1.0.2

- [FIXED] Added PyYAML library as a dependency to resolve Github service issue.

# 1.0.1

- [FIXED] Added external evidence as a valid evidence type to evidence map.

# 1.0.0

- [NEW] Make the Auditree Framework public.
