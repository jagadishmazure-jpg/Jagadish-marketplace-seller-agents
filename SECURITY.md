# Security policy

This is a synthetic demo repository: no production systems, no real user
data, no credentials. If you find a genuine security issue in the demo
code, please open a GitHub issue — do not include any personal data.

- No secrets are committed; CI scans history with gitleaks.
- The SQL gateway is SELECT-only by construction (SEC-SELECT-01/02/03).
- User feedback text is PII-scrubbed before storage.
