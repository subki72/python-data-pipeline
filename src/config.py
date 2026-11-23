"""Validated environment-backed configuration for the Fashion ETL pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import re
from typing import Mapping, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://fashion-studio.dicoding.dev"
DEFAULT_MAX_PAGES = 50
DEFAULT_OUTPUT_CSV_PATH = "data/products.csv"
DEFAULT_GOOGLE_CREDS_PATH = "credentials/google-sheets-api.json"
DEFAULT_SPREADSHEET_NAME = "ETL-Submission-Project"
DEFAULT_DB_TABLE = "fashion_products"
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_FACTOR = 0.5
DEFAULT_LOG_LEVEL = "INFO"

MAX_ALLOWED_PAGES = 500
MAX_ALLOWED_TIMEOUT = 120.0
MAX_ALLOWED_RETRIES = 10

VALID_LOG_LEVELS: frozenset[str] = frozenset({
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
})
ALLOWED_DB_SCHEMES: frozenset[str] = frozenset({
    "postgresql",
    "postgresql+psycopg2",
    "sqlite",
})
SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigValidationError(ValueError):
    """Raised when one or more pipeline configuration values fail validation."""


def _parse_int_env(env: Mapping[str, str], key: str, default: int) -> int:
    """Parse an integer environment variable with explicit error reporting."""
    raw_value = env.get(key)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return int(raw_value.strip())
    except ValueError as exc:
        raise ConfigValidationError(f"Environment variable {key} must be an integer.") from exc


def _parse_float_env(env: Mapping[str, str], key: str, default: float) -> float:
    """Parse a float environment variable with explicit error reporting."""
    raw_value = env.get(key)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return float(raw_value.strip())
    except ValueError as exc:
        raise ConfigValidationError(f"Environment variable {key} must be a numeric value.") from exc


def _validate_http_url(url: str, field_name: str) -> Optional[str]:
    """Validate that an external HTTP(S) URL contains scheme and hostname."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"{field_name} must be a valid http:// or https:// URL."
    return None


def _validate_database_settings(db_url: Optional[str], db_table: str) -> list[str]:
    """Validate database connection scheme and target SQL table identifier."""
    errors: list[str] = []
    if not SQL_IDENTIFIER_PATTERN.match(db_table):
        errors.append("DB_TABLE must be a valid SQL identifier (alphanumeric and underscores).")
    if db_url:
        parsed = urlparse(db_url)
        if parsed.scheme not in ALLOWED_DB_SCHEMES:
            allowed = ", ".join(sorted(ALLOWED_DB_SCHEMES))
            errors.append(f"DB_URL scheme '{parsed.scheme}' is unsupported; expected one of: {allowed}.")
    return errors


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable runtime settings for the Fashion ETL pipeline.

    Attributes:
        base_url: Root URL of the product catalog to scrape.
        max_pages: Maximum number of catalog pages to traverse.
        output_csv_path: Target path for the local CSV sink.
        google_creds_path: Path to the Google service account JSON keyfile.
        spreadsheet_name: Target Google Sheets workbook title.
        db_url: Optional SQLAlchemy database connection URL.
        db_table: Destination SQL table name.
        request_timeout: Per-request HTTP timeout in seconds.
        max_retries: Maximum retry attempts on transient HTTP errors.
        retry_backoff_factor: Exponential backoff multiplier in seconds.
        log_level: Root logging level name.
    """

    base_url: str = DEFAULT_BASE_URL
    max_pages: int = DEFAULT_MAX_PAGES
    output_csv_path: str = DEFAULT_OUTPUT_CSV_PATH
    google_creds_path: str = DEFAULT_GOOGLE_CREDS_PATH
    spreadsheet_name: str = DEFAULT_SPREADSHEET_NAME
    db_url: Optional[str] = None
    db_table: str = DEFAULT_DB_TABLE
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "PipelineConfig":
        """Build and validate a PipelineConfig from environment variables.

        Args:
            env: Optional mapping overriding ``os.environ`` (useful in tests).

        Returns:
            A validated ``PipelineConfig`` instance.

        Raises:
            ConfigValidationError: If any setting is malformed or out of bounds.
        """
        source = os.environ if env is None else env
        raw_db_url = source.get("DB_URL", "").strip()
        config = cls(
            base_url=source.get("BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/"),
            max_pages=_parse_int_env(source, "MAX_PAGES", DEFAULT_MAX_PAGES),
            output_csv_path=source.get("OUTPUT_CSV_PATH", DEFAULT_OUTPUT_CSV_PATH).strip(),
            google_creds_path=source.get("GOOGLE_CREDS_PATH", DEFAULT_GOOGLE_CREDS_PATH).strip(),
            spreadsheet_name=source.get("SPREADSHEET_NAME", DEFAULT_SPREADSHEET_NAME).strip(),
            db_url=raw_db_url or None,
            db_table=source.get("DB_TABLE", DEFAULT_DB_TABLE).strip(),
            request_timeout=_parse_float_env(source, "REQUEST_TIMEOUT", DEFAULT_REQUEST_TIMEOUT),
            max_retries=_parse_int_env(source, "MAX_RETRIES", DEFAULT_MAX_RETRIES),
            retry_backoff_factor=_parse_float_env(
                source, "RETRY_BACKOFF_FACTOR", DEFAULT_RETRY_BACKOFF_FACTOR
            ),
            log_level=source.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper(),
        )
        config.validate()
        logger.info("Loaded validated pipeline configuration for base_url=%s", config.base_url)
        return config

    def validate(self) -> None:
        """Validate all configuration invariants and fail fast on invalid settings.

        Raises:
            ConfigValidationError: If any field violates schema or safety bounds.
        """
        errors: list[str] = []
        url_error = _validate_http_url(self.base_url, "BASE_URL")
        if url_error:
            errors.append(url_error)
        if not 1 <= self.max_pages <= MAX_ALLOWED_PAGES:
            errors.append(f"MAX_PAGES must be between 1 and {MAX_ALLOWED_PAGES}.")
        if not self.output_csv_path:
            errors.append("OUTPUT_CSV_PATH must not be empty.")
        if not self.google_creds_path:
            errors.append("GOOGLE_CREDS_PATH must not be empty.")
        if not self.spreadsheet_name:
            errors.append("SPREADSHEET_NAME must not be empty.")
        if not 0 < self.request_timeout <= MAX_ALLOWED_TIMEOUT:
            errors.append(f"REQUEST_TIMEOUT must be > 0 and <= {MAX_ALLOWED_TIMEOUT} seconds.")
        if not 0 <= self.max_retries <= MAX_ALLOWED_RETRIES:
            errors.append(f"MAX_RETRIES must be between 0 and {MAX_ALLOWED_RETRIES}.")
        if self.retry_backoff_factor < 0:
            errors.append("RETRY_BACKOFF_FACTOR must be non-negative.")
        if self.log_level not in VALID_LOG_LEVELS:
            errors.append(f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}.")
        errors.extend(_validate_database_settings(self.db_url, self.db_table))

        if errors:
            raise ConfigValidationError("; ".join(errors))

    def masked_db_url(self) -> str:
        """Return a credential-redacted database URL safe for structured logs."""
        if not self.db_url:
            return "<unset>"
        parsed = urlparse(self.db_url)
        host = parsed.hostname or "unknown-host"
        port_segment = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://***@{host}{port_segment}{parsed.path}"
