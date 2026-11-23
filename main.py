"""CLI orchestrator entrypoint for the Fashion Studio ETL pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Optional

from dotenv import load_dotenv
import pandas as pd

from src.config import ConfigValidationError, PipelineConfig
from src.extract import scrape_fashion_data
from src.health import PipelineErrorHandler, check_pipeline_health, configure_logging
from src.load import save_to_csv, save_to_google_sheets, save_to_postgresql
from src.transform import clean_data

logger = logging.getLogger(__name__)


def _load_to_sinks(
    clean_df: pd.DataFrame,
    config: PipelineConfig,
    error_handler: PipelineErrorHandler,
    *,
    skip_google_sheets: bool,
    skip_postgresql: bool,
) -> dict[str, bool]:
    """Execute all enabled downstream load sinks with isolated error boundaries."""
    results: dict[str, bool] = {
        "csv": False,
        "google_sheets": False,
        "postgresql": False,
    }

    with error_handler.capture("load:csv"):
        results["csv"] = save_to_csv(clean_df, config.output_csv_path)

    if not skip_google_sheets:
        with error_handler.capture("load:google_sheets"):
            results["google_sheets"] = save_to_google_sheets(
                clean_df,
                config.google_creds_path,
                config.spreadsheet_name,
            )

    if not skip_postgresql and config.db_url:
        with error_handler.capture("load:postgresql"):
            results["postgresql"] = save_to_postgresql(
                clean_df,
                config.db_url,
                config.db_table,
            )
    elif not skip_postgresql:
        logger.warning("DB_URL is not configured; skipping PostgreSQL load sink.")

    return results


def _build_pipeline_summary(
    status: str,
    extracted_rows: int,
    cleaned_rows: int,
    sinks: dict[str, bool],
    health_report: dict[str, Any],
    error_handler: PipelineErrorHandler,
) -> dict[str, Any]:
    """Assemble a consistent structured summary payload for a pipeline run."""
    return {
        "status": status,
        "extracted_rows": extracted_rows,
        "cleaned_rows": cleaned_rows,
        "sinks": sinks,
        "health": health_report,
        "errors": error_handler.summary(),
    }


def run_pipeline(
    config: Optional[PipelineConfig] = None,
    *,
    skip_google_sheets: bool = False,
    skip_postgresql: bool = False,
) -> dict[str, Any]:
    """Run the full Extract -> Transform -> Load workflow end to end.

    Args:
        config: Optional pre-validated ``PipelineConfig``. Loads from ``.env``
            and process environment when omitted.
        skip_google_sheets: Disable uploading to Google Sheets when True.
        skip_postgresql: Disable loading into PostgreSQL when True.

    Returns:
        Structured summary dictionary containing row counts, sink statuses,
        pre-flight health report, and captured errors.
    """
    load_dotenv()
    error_handler = PipelineErrorHandler()
    active_config = config if config is not None else PipelineConfig.from_env()
    configure_logging(active_config.log_level)

    logger.info("Starting ETL pipeline for source=%s", active_config.base_url)
    health_report = check_pipeline_health(active_config)
    raw_df = scrape_fashion_data(
        base_url=active_config.base_url,
        max_pages=active_config.max_pages,
        timeout=active_config.request_timeout,
        max_retries=active_config.max_retries,
        backoff_factor=active_config.retry_backoff_factor,
    )
    clean_df = clean_data(raw_df)

    if clean_df is None or clean_df.empty:
        logger.warning("Pipeline stopped because transformed dataset is empty.")
        empty_sinks = {"csv": False, "google_sheets": False, "postgresql": False}
        return _build_pipeline_summary("empty", len(raw_df), 0, empty_sinks, health_report, error_handler)

    sink_results = _load_to_sinks(
        clean_df,
        active_config,
        error_handler,
        skip_google_sheets=skip_google_sheets,
        skip_postgresql=skip_postgresql,
    )
    logger.info("ETL pipeline completed: cleaned_rows=%d sinks=%s", len(clean_df), sink_results)
    return _build_pipeline_summary("completed", len(raw_df), len(clean_df), sink_results, health_report, error_handler)


def _build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for the pipeline entrypoint."""
    parser = argparse.ArgumentParser(description="Fashion Studio Automated ETL Pipeline")
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run pre-flight /health readiness diagnostics and exit.",
    )
    parser.add_argument(
        "--skip-google-sheets",
        action="store_true",
        help="Skip uploading transformed records to Google Sheets.",
    )
    parser.add_argument(
        "--skip-postgresql",
        action="store_true",
        help="Skip loading transformed records into PostgreSQL.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint supporting both pipeline execution and health probes."""
    args = _build_arg_parser().parse_args(argv)
    load_dotenv()

    if args.health:
        report = check_pipeline_health()
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        return 0 if report["status"] in {"healthy", "degraded"} else 1

    try:
        summary = run_pipeline(
            skip_google_sheets=args.skip_google_sheets,
            skip_postgresql=args.skip_postgresql,
        )
        return 0 if summary["status"] in {"completed", "empty"} else 1
    except ConfigValidationError as exc:
        configure_logging("ERROR")
        logger.error("Configuration validation failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
