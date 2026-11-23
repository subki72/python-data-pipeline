"""Load stage: validated sinks for local CSV, Google Sheets, and PostgreSQL."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Optional, Union
from urllib.parse import urlparse

from google.oauth2.service_account import Credentials
import gspread
from gspread.exceptions import GSpreadException
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

GOOGLE_SHEETS_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
ALLOWED_DB_SCHEMES: frozenset[str] = frozenset({
    "postgresql",
    "postgresql+psycopg2",
    "sqlite",
})
SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_DB_CONNECT_TIMEOUT = 10


def _is_loadable_dataframe(df: Optional[pd.DataFrame]) -> bool:
    """Return True when df is a non-empty pandas DataFrame."""
    return isinstance(df, pd.DataFrame) and not df.empty


def validate_table_name(table_name: str) -> str:
    """Validate that a target SQL table name is a safe identifier.

    Args:
        table_name: Candidate destination table name.

    Returns:
        Stripped table name when valid.

    Raises:
        ValueError: If ``table_name`` contains disallowed SQL characters.
    """
    cleaned = table_name.strip()
    if not cleaned or not SQL_IDENTIFIER_PATTERN.match(cleaned):
        raise ValueError(
            "Invalid table_name: only alphanumeric characters and underscores are permitted."
        )
    return cleaned


def validate_db_url(db_url: str) -> str:
    """Validate that a SQLAlchemy database connection string uses an allowed scheme.

    Args:
        db_url: SQLAlchemy connection URL.

    Returns:
        Stripped database URL.

    Raises:
        ValueError: If ``db_url`` is empty or uses an unsupported scheme.
    """
    cleaned = db_url.strip() if isinstance(db_url, str) else ""
    if not cleaned:
        raise ValueError("Database URL must not be empty.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ALLOWED_DB_SCHEMES:
        allowed = ", ".join(sorted(ALLOWED_DB_SCHEMES))
        raise ValueError(f"Unsupported DB_URL scheme '{parsed.scheme}'; expected one of: {allowed}.")
    return cleaned


def save_to_csv(
    df: Optional[pd.DataFrame],
    filename: Union[str, Path] = "products.csv",
) -> bool:
    """Persist a cleaned DataFrame to a local CSV file.

    Args:
        df: Cleaned product ``DataFrame``.
        filename: Target CSV output file path.

    Returns:
        ``True`` if the CSV file was written successfully, ``False`` otherwise.
    """
    if not _is_loadable_dataframe(df):
        logger.warning("Skipping CSV load: input DataFrame is empty or None.")
        return False

    target_str = str(filename).strip()
    if not target_str:
        logger.error("Failed to save to CSV: filename must not be empty.")
        return False

    try:
        assert df is not None  # Guarded by _is_loadable_dataframe
        parent_dir = Path(target_str).parent
        if str(parent_dir) not in ("", "."):
            parent_dir.mkdir(parents=True, exist_ok=True)

        df.to_csv(target_str, index=False)
        logger.info("Saved %d rows to CSV at %s", len(df), target_str)
        return True
    except (OSError, ValueError) as exc:
        logger.error("Failed to save to CSV (%s): %s", target_str, exc)
        return False


def save_to_google_sheets(
    df: Optional[pd.DataFrame],
    json_keyfile: Union[str, Path] = "google-sheets-api.json",
    spreadsheet_name: str = "Fashion_Data",
) -> bool:
    """Upload a cleaned DataFrame to the first worksheet of a Google Sheet.

    Args:
        df: Cleaned product ``DataFrame``.
        json_keyfile: Path to the Google service account JSON credentials file.
        spreadsheet_name: Exact Google Sheets workbook title.

    Returns:
        ``True`` if rows were uploaded successfully, ``False`` otherwise.
    """
    if not _is_loadable_dataframe(df):
        logger.warning("Skipping Google Sheets load: input DataFrame is empty or None.")
        return False

    keyfile_str = str(json_keyfile).strip()
    sheet_title = spreadsheet_name.strip()
    if not keyfile_str or not sheet_title:
        logger.error("Failed to save to Google Sheets: keyfile and spreadsheet_name are required.")
        return False

    try:
        assert df is not None  # Guarded by _is_loadable_dataframe
        credentials = Credentials.from_service_account_file(
            keyfile_str,
            scopes=GOOGLE_SHEETS_SCOPES,
        )
        client = gspread.authorize(credentials)

        sheet = client.open(sheet_title).sheet1
        sheet.clear()
        payload = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(payload)

        logger.info("Saved %d rows to Google Sheets workbook '%s'", len(df), sheet_title)
        return True
    except (OSError, ValueError, GSpreadException) as exc:
        logger.error("Failed to save to Google Sheets workbook '%s': %s", sheet_title, exc)
        return False


def _build_engine_kwargs(db_url: str, connect_timeout: int) -> dict[str, object]:
    """Build SQLAlchemy engine kwargs with explicit connect_timeout for PostgreSQL."""
    if db_url.startswith("postgresql"):
        return {"connect_args": {"connect_timeout": connect_timeout}}
    return {}


def save_to_postgresql(
    df: Optional[pd.DataFrame],
    db_url: str,
    table_name: str = "fashion_products",
    connect_timeout: int = DEFAULT_DB_CONNECT_TIMEOUT,
) -> bool:
    """Load a cleaned DataFrame into a PostgreSQL (or compatible SQL) table.

    Args:
        df: Cleaned product ``DataFrame``.
        db_url: SQLAlchemy connection string.
        table_name: Validated destination SQL table name.
        connect_timeout: Connection timeout in seconds for PostgreSQL engines.

    Returns:
        ``True`` if rows were written successfully, ``False`` otherwise.
    """
    if not _is_loadable_dataframe(df):
        logger.warning("Skipping PostgreSQL load: input DataFrame is empty or None.")
        return False

    engine = None
    try:
        assert df is not None  # Guarded by _is_loadable_dataframe
        validated_url = validate_db_url(db_url)
        validated_table = validate_table_name(table_name)
        engine_kwargs = _build_engine_kwargs(validated_url, connect_timeout)

        engine = create_engine(validated_url, **engine_kwargs)
        df.to_sql(validated_table, engine, if_exists="replace", index=False)

        logger.info("Saved %d rows to PostgreSQL table '%s'", len(df), validated_table)
        return True
    except (ValueError, SQLAlchemyError, OSError) as exc:
        logger.error("Failed to save to PostgreSQL table '%s': %s", table_name, exc)
        return False
    finally:
        if engine is not None:
            engine.dispose()
