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

## MVP Application Hardening

The MVP API includes these baseline protections:

- Passwords are stored with bcrypt hashes, never in plaintext.
- API tokens are signed JWT access tokens with `exp`, `iat`, and token type claims.
- Production-like environments must use a strong `SECRET_KEY`, non-default admin password, and explicit CORS origins.
- Login and registration endpoints use basic in-memory throttling to reduce brute-force attempts.
- API responses include browser security headers for MIME sniffing, clickjacking, referrer, permissions, and same-origin resource policy.
- Uploads are constrained by extension, file size, batch size, image magic bytes, and upload-root path containment.
- User-facing API errors hide raw server-side 5xx response bodies.

Deployment still needs HTTPS termination, secret rotation, database/network firewalling, dependency vulnerability monitoring, backups, and environment-specific logging review. No application can be guaranteed impossible to hack; treat this policy as the current baseline and keep testing it as the deployment changes.
