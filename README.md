# Python Data Pipeline — Fashion Studio ETL

[![CI Pipeline](https://github.com/subki72/python-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/subki72/python-data-pipeline/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style: Ruff & Flake8](https://img.shields.io/badge/code%20style-ruff%20%26%20flake8-black.svg)](pyproject.toml)

Production-ready automated ETL (Extract, Transform, Load) pipeline built in Python. It scrapes paginated fashion catalog listings with bounded exponential-backoff retries, validates and normalizes records into typed schemas, and loads clean datasets into three independent sinks:

1. **Local CSV** (`data/products.csv`)
2. **Google Sheets** (via Google Service Account credentials)
3. **PostgreSQL** (via SQLAlchemy with managed schema migration)

## ETL Architecture

```text
python-data-pipeline/
├── .github/
│   ├── workflows/ci.yml            # Lint, Mypy, Pytest coverage, Docker build, Semgrep, Trivy
│   └── dependabot.yml              # Weekly pip, Docker, and GitHub Actions security updates
├── docs/
│   └── RUNBOOK.md                  # Production health checks, troubleshooting, and rollback guide
├── migrations/
│   └── 001_create_fashion_products.sql  # Idempotent PostgreSQL destination table schema
├── src/
│   ├── __init__.py
│   ├── config.py                   # Validated PipelineConfig loader and secret redaction
│   ├── health.py                   # /health readiness checker, error boundary, structured logging
│   ├── extract.py                  # Paginated HTML scraper with timeouts and retry backoff
│   ├── transform.py                # Schema validation, deduplication, currency conversion
│   └── load.py                     # Hardened CSV, Google Sheets, and PostgreSQL sinks
├── tests/
│   ├── test_config.py              # Configuration validation and redaction unit tests
│   ├── test_extract.py             # Scraper parsing and retry resilience unit tests
│   ├── test_transform.py           # Filtering and normalization unit tests
│   ├── test_load.py                # Sink loaders and SQL identifier guard tests
│   └── test_pipeline_integration.py  # Mocked end-to-end ETL and /health integration tests
├── Dockerfile                      # Multi-stage non-root runtime container with HEALTHCHECK
├── docker-compose.yml              # Local pipeline + PostgreSQL 16 stack
├── Makefile                        # Standardized local workflow automation
├── pyproject.toml                  # PEP 621 metadata, Ruff, Pytest, Coverage, Mypy config
├── requirements.txt                # Pinned runtime dependencies
├── requirements-lock.txt           # Fully resolved transitive dependency lockfile
├── uv.lock                         # Reproducible uv lockfile
├── .env.example                    # Externalized configuration template
└── main.py                         # CLI orchestrator supporting ETL execution and --health
```

### Data Flow

```text
[Catalog Pages] --(HTTP + Retry/Timeout)--> [src/extract.py]
                                                   |
                                           Raw DataFrame
                                                   v
                                           [src/transform.py] (Validate, Filter, USD->IDR, UTC)
                                                   |
                                          Clean DataFrame
                                                   v
                                           [src/load.py] ---> CSV | Google Sheets | PostgreSQL
```

## Quickstart

### Local Development with Makefile

1. **Clone and prepare environment**:
   ```bash
   git clone https://github.com/subki72/python-data-pipeline.git
   cd python-data-pipeline
   cp .env.example .env
   ```
2. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
   make install
   ```
3. **Run pre-flight health check and execute the pipeline**:
   ```bash
   make health
   make run
   ```

### Running with Docker Compose

Launch PostgreSQL (auto-initialized from `migrations/001_create_fashion_products.sql`) together with the hardened non-root ETL container:

```bash
make docker-up
```

Tear down containers and volumes when finished:

```bash
make docker-down
```

## Configuration

All runtime settings are externalized through environment variables (documented in `.env.example` and enforced by `PipelineConfig.validate()`):

| Variable | Default | Purpose |
|---|---|---|
| `BASE_URL` | `https://fashion-studio.dicoding.dev` | Source storefront HTTP(S) root URL |
| `MAX_PAGES` | `50` | Maximum catalog pages to scrape (`1..500`) |
| `REQUEST_TIMEOUT` | `10` | Per-request HTTP timeout in seconds |
| `MAX_RETRIES` | `3` | Retry attempts on transient HTTP failures |
| `RETRY_BACKOFF_FACTOR` | `0.5` | Exponential backoff multiplier in seconds |
| `OUTPUT_CSV_PATH` | `data/products.csv` | Local CSV destination path |
| `GOOGLE_CREDS_PATH` | `credentials/google-sheets-api.json` | Google service account keyfile path |
| `SPREADSHEET_NAME` | `ETL-Submission-Project` | Target Google Sheets workbook title |
| `DB_URL` | *(unset)* | SQLAlchemy PostgreSQL connection URL |
| `DB_TABLE` | `fashion_products` | Validated destination SQL table name |
| `LOG_LEVEL` | `INFO` | Structured log verbosity level |

## Testing & Quality Gates

Run the full automated quality suite using `Makefile` targets:

```bash
make lint       # Flake8 (<=120 chars) + Ruff checks
make typecheck  # Static type verification with Mypy
make test       # Unit and integration tests via Pytest
make coverage   # Pytest with >=80% coverage gate over src/
```

## Security & Governance

- **Secret Hygiene**: `.env`, `.env.*`, `credentials/`, and keyfiles are strictly excluded in `.gitignore`. Database credentials are redacted in all log messages.
- **Vulnerability Management**: Automated weekly Dependabot updates (`semver-major` ignored), Semgrep SAST, and Trivy container scanning run in CI. See [SECURITY.md](SECURITY.md) for disclosure instructions.
- **Operations & Contributions**: Consult [docs/RUNBOOK.md](docs/RUNBOOK.md) for incident playbooks, [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines, [CHANGELOG.md](CHANGELOG.md) for release history, and [LICENSE](LICENSE) for MIT licensing terms.
