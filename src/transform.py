"""Transform stage: schema validation, filtering, and normalization for product data."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Title",
    "Price",
    "Rating",
    "Colors",
    "Size",
    "Gender",
)
USD_TO_IDR_RATE: float = 16000.0
INVALID_TITLE_TOKEN = "Unknown Product"
INVALID_PRICE_TOKEN = "Price Unavailable"
INVALID_RATING_TOKEN = "Invalid Rating"


def validate_raw_dataframe(df: Optional[pd.DataFrame]) -> None:
    """Validate that raw extracted data is a non-empty DataFrame with required columns.

    Args:
        df: Candidate raw product DataFrame.

    Raises:
        ValueError: If the DataFrame is ``None``, not a ``pd.DataFrame``, empty,
            or missing required schema columns.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("Input data must be a pandas DataFrame.")
    if df.empty:
        raise ValueError("Input DataFrame is empty.")

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Input DataFrame missing required columns: {', '.join(missing_columns)}")


def _filter_invalid_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop null, duplicate, and sentinel placeholder product rows."""
    cleaned = df.dropna(subset=list(REQUIRED_COLUMNS)).copy()
    cleaned = cleaned.drop_duplicates(keep="first")

    cleaned = cleaned[
        ~cleaned["Title"].astype(str).str.contains(INVALID_TITLE_TOKEN, case=False, na=False)
    ]
    cleaned = cleaned[
        ~cleaned["Price"].astype(str).str.contains(INVALID_PRICE_TOKEN, case=False, na=False)
    ]
    cleaned = cleaned[
        ~cleaned["Rating"].astype(str).str.contains(INVALID_RATING_TOKEN, case=False, na=False)
    ]
    return cleaned


def _normalize_columns(df: pd.DataFrame, exchange_rate: float) -> pd.DataFrame:
    """Convert raw string columns into typed analytical fields with UTC timestamp."""
    normalized = df.copy()

    price_text = (
        normalized["Price"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    normalized["Price"] = pd.to_numeric(price_text, errors="coerce") * exchange_rate

    rating_extracted = normalized["Rating"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
    normalized["Rating"] = pd.to_numeric(rating_extracted, errors="coerce").astype(float)

    colors_extracted = normalized["Colors"].astype(str).str.extract(r"(\d+)")[0]
    normalized["Colors"] = pd.to_numeric(colors_extracted, errors="coerce").astype("Int64")

    normalized["Size"] = (
        normalized["Size"].astype(str).str.replace("Size:", "", case=False, regex=False).str.strip()
    )
    normalized["Gender"] = (
        normalized["Gender"]
        .astype(str)
        .str.replace("Gender:", "", case=False, regex=False)
        .str.strip()
    )

    normalized = normalized.dropna(subset=["Price", "Rating", "Colors"]).reset_index(drop=True)
    normalized["timestamp"] = datetime.now(timezone.utc)
    return normalized


def clean_data(
    df: Optional[pd.DataFrame],
    exchange_rate: float = USD_TO_IDR_RATE,
) -> Optional[pd.DataFrame]:
    """Clean, validate, and normalize extracted fashion catalog records.

    Args:
        df: Raw extracted product ``DataFrame``.
        exchange_rate: USD-to-IDR conversion multiplier (defaults to ``16000.0``).

    Returns:
        Cleaned ``DataFrame`` with typed columns and UTC ``timestamp``, or ``None``
        when input validation or parsing fails.
    """
    if exchange_rate <= 0:
        logger.error("Invalid exchange_rate=%s; must be positive.", exchange_rate)
        return None

    try:
        validate_raw_dataframe(df)
        assert df is not None  # Narrowed by validate_raw_dataframe
        initial_count = len(df)

        filtered = _filter_invalid_rows(df)
        if filtered.empty:
            logger.warning("All %d raw rows were filtered out as invalid.", initial_count)
            return filtered

        cleaned = _normalize_columns(filtered, exchange_rate=exchange_rate)
        logger.info(
            "Transformed %d raw rows into %d clean records",
            initial_count,
            len(cleaned),
        )
        return cleaned
    except (ValueError, TypeError, KeyError) as exc:
        logger.error("Error occurred during data transformation: %s", exc)
        return None
