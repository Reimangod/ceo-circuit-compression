# Security and sensitive information

This is a private research repository. Access to the checkout does not authorize
redistribution of private correspondence, third-party material, or credentials.

Report suspected credential disclosure or a security-sensitive issue privately
to the repository owner before opening an issue. Do not include tokens, private
keys, full personal paths, or private research payloads in logs or reports.

For ordinary reproducibility failures, use the bug-report template with a minimal
command, commit, Python version, and sanitized error message. The fixed data
archive is identified by checksums, so a file digest is usually more useful than
copying the file into an issue.

CI uses read-only repository permissions and scoped release-download credentials.
Private release verification is disabled for pull requests from forks. The
workflow does not use `pull_request_target`, modify releases, or launch new
molecular searches. These controls reduce accidental access and mutation; they
are not a guarantee that arbitrary research code is safe to run.
