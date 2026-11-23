# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `python-data-pipeline`:

1. **Do NOT open a public GitHub issue** for undisclosed vulnerabilities.
2. Submit a private report via GitHub Security Advisories (`Security -> Advisories -> Report a vulnerability`).
3. Include affected file paths, line numbers, reproduction steps, and estimated severity.
4. Initial acknowledgement will be provided within **48 hours**.

## Security Controls

- **Secret Hygiene**: `.env`, `.env.*`, `credentials/`, and service account JSON keyfiles are excluded via `.gitignore`; database URLs are redacted in logs via `PipelineConfig.masked_db_url()`.
- **Input & Identifier Validation**: External URLs, SQL table identifiers (`^[A-Za-z_][A-Za-z0-9_]*$`), database connection schemes, and numeric pipeline bounds are strictly validated before execution.
- **Automated Vulnerability Management**: Weekly Dependabot alerts (`pip`, `docker`, `github-actions` with `semver-major` ignored for stability), Semgrep SAST, and Trivy container image scanning in CI.
- **Container Hardening**: Multi-stage non-root Docker builds (`USER appuser`, UID/GID `10001`) with built-in `/health` readiness checks.
