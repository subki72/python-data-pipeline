# Changelog

All notable changes to `python-data-pipeline` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-23

### Added
- Environment-backed, strictly validated `PipelineConfig` in `src/config.py` with credential redaction (`masked_db_url`) and `.env.example` template.
- Operational observability layer in `src/health.py` providing structured `/health` pre-flight readiness diagnostics, centralized `PipelineErrorHandler`, and `configure_logging()`.
- CLI flags in `main.py` (`--health`, `--skip-google-sheets`, `--skip-postgresql`) with structured summary output.
- Exponential backoff retry resilience and `HTTPAdapter` session builder in `src/extract.py`.
- Unit and integration test suites (`tests/test_config.py`, `tests/test_pipeline_integration.py`) covering full mocked ETL execution, retry recovery, validation guards, and health checks.
- Reproducible lockfiles (`uv.lock`, `requirements-lock.txt`), `pyproject.toml`, `.flake8`, and `.pre-commit-config.yaml`.
- GitHub Actions CI pipeline (Flake8, Ruff, Mypy, Pytest with coverage gate, Docker build, Semgrep SAST, Trivy) and weekly Dependabot updates.
- Hardened multi-stage non-root `Dockerfile`, `docker-compose.yml` (app + PostgreSQL), SQL migration (`migrations/001_create_fashion_products.sql`), and `Makefile`.
- Governance and operational documentation (`LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/RUNBOOK.md`).

### Changed
- Replaced all raw `print()` statements across `main.py` and `src/` with structured leveled `logging.getLogger(__name__)`.
- Added complete Python 3.11 type annotations, Google-style docstrings, and input validation guard clauses across all ETL modules.
- Guaranteed SQLAlchemy engine disposal via `try/finally` and explicit PostgreSQL connection timeouts in `src/load.py`.

## [0.1.0] - 2026-05-01

### Added
- Initial POC implementation of the Fashion Studio ETL pipeline (`extract.py`, `transform.py`, `load.py`, `main.py`) with baseline unit tests.
