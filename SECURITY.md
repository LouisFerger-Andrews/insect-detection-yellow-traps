# Security Policy

## Reporting a Vulnerability

Please do not open public issues for security vulnerabilities.

Report vulnerabilities privately using one of these channels:
- GitHub Security Advisory (preferred)
- Direct contact with project maintainers

Include:
- affected component/path
- reproduction steps or proof-of-concept
- severity/impact
- suggested mitigation (if known)

## Response Targets

- Initial acknowledgment: within 72 hours
- Triage decision: within 7 days
- Fix timeline: based on severity and exploitability

## Supported Versions

Security fixes are prioritized for the current `main` branch.

## Sensitive Data Rules

- Never commit API keys, credentials, or production secrets.
- Never commit raw user/sensor datasets under `04_modeling_experimental/data/raw`.
- Rotate credentials immediately if exposure is suspected.
- If secrets are committed, rewrite history and force push after remediation.
