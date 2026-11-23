# Operational Runbook — Fashion Studio ETL Pipeline

## Service Overview

`python-data-pipeline` is a containerized batch ETL service that extracts product catalog listings from the configured storefront (`BASE_URL`), cleans and normalizes fields (`src/transform.py`), and loads validated output into three sinks:

1. Local CSV (`OUTPUT_CSV_PATH`)
2. Google Sheets (`SPREADSHEET_NAME` via service account JSON)
3. PostgreSQL (`DB_URL` / `DB_TABLE`)

## Pre-Flight Health Checks

Verify configuration validity, CSV output directory permissions, credential file presence, and database configuration before triggering a batch run:

```bash
python main.py --health
```

### Health Status Semantics (`/health`)

| Status | Exit Code | Meaning | Action |
|---|:---:|---|---|
| `healthy` | `0` | Config valid, CSV output writable, Google credentials file found, `DB_URL` configured | Safe for full 3-sink batch run |
| `degraded` | `0` | Config valid and CSV output writable, but one or more optional external sinks (Google Sheets / PostgreSQL) are unconfigured | Safe for CSV-only run or configure missing external credentials |
| `unhealthy` | `1` | Invalid configuration or unwritable CSV output path | Inspect stderr/JSON output and fix `.env` or mount permissions |

## Standard Operations

### Run Full Pipeline Locally

```bash
make health
make run
```

### Run Selectively (Skip External Sinks)

```bash
python main.py --skip-google-sheets
python main.py --skip-postgresql
```

### Run via Docker Compose (App + PostgreSQL)

```bash
docker compose up --build
```

The PostgreSQL container automatically applies `migrations/001_create_fashion_products.sql` on initial volume creation.

## Configuration Reference

| Variable | Default | Required | Description |
|---|---|:---:|---|
| `BASE_URL` | `https://fashion-studio.dicoding.dev` | No | Target catalog HTTP(S) base URL |
| `MAX_PAGES` | `50` | No | Catalog pages to scrape (`1..500`) |
| `REQUEST_TIMEOUT` | `10` | No | Per-request HTTP timeout in seconds (`>0..120`) |
| `MAX_RETRIES` | `3` | No | Retry attempts per page on transient errors (`0..10`) |
| `RETRY_BACKOFF_FACTOR` | `0.5` | No | Exponential backoff multiplier in seconds (`>=0`) |
| `OUTPUT_CSV_PATH` | `data/products.csv` | No | Destination CSV file path |
| `GOOGLE_CREDS_PATH` | `credentials/google-sheets-api.json` | For Sheets | Service account JSON path (never committed) |
| `SPREADSHEET_NAME` | `ETL-Submission-Project` | For Sheets | Google Sheets workbook title |
| `DB_URL` | *(unset)* | For Postgres | SQLAlchemy PostgreSQL connection string |
| `DB_TABLE` | `fashion_products` | For Postgres | Safe SQL destination table identifier |
| `LOG_LEVEL` | `INFO` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

## Incident Response & Troubleshooting

### 1. Upstream Scraping Timeouts or HTTP 429/5xx
- **Symptom**: Warning logs `HTTP error fetching page=...` followed by `Exhausted N attempts`.
- **Cause**: Source storefront rate-limiting or transient network outage.
- **Remediation**: Increase `REQUEST_TIMEOUT` (e.g. `20`), `MAX_RETRIES` (e.g. `5`), and `RETRY_BACKOFF_FACTOR` (e.g. `1.0`), then re-run.

### 2. Google Sheets Authentication or Quota Errors
- **Symptom**: `Failed to save to Google Sheets workbook ...` while CSV and PostgreSQL succeed.
- **Cause**: Missing `credentials/google-sheets-api.json`, expired service account key, or missing Editor share permission on the target workbook.
- **Remediation**: Verify keyfile mount permissions and share the sheet with the service account email. Re-run or execute with `--skip-google-sheets` to isolate the incident.

### 3. PostgreSQL Connection Failure
- **Symptom**: `Failed to save to PostgreSQL table ...` with `SQLAlchemyError`.
- **Cause**: Database unreachable, wrong credentials, SSL mismatch, or invalid `DB_TABLE` identifier.
- **Remediation**: Run `python main.py --health` to confirm `database_config.configured` is `true` and inspect the redacted target host. Confirm PostgreSQL readiness (`pg_isready`) and re-run.

### 4. Empty Transformed Dataset
- **Symptom**: Warning `Pipeline stopped because transformed dataset is empty.`
- **Cause**: Upstream HTML markup changed or all scraped rows contained sentinel values (`Unknown Product`, `Price Unavailable`, `Invalid Rating`).
- **Remediation**: Inspect a live page's `.collection-card` markup against `src/extract.py` selectors and verify existing downstream tables were intentionally preserved (load sinks are skipped automatically on empty data).

## Rollback & Recovery

- **Code Rollback**: Redeploy the previous signed Git tag (`git checkout v1.0.0`) and rebuild the Docker image (`make docker-build`).
- **Data Recovery**: The local CSV artifact (`data/products.csv`) acts as an immediate fallback snapshot; restore PostgreSQL from the latest `pg_dump` backup before re-running if partial table replacement occurred.
