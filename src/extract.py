"""Extract stage: resilient web scraping for the Fashion Studio product catalog."""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://fashion-studio.dicoding.dev"
DEFAULT_MAX_PAGES = 50
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)
DETAIL_FIELD_MARKERS: tuple[tuple[str, str], ...] = (
    ("Rating", "Rating:"),
    ("Colors", "Colors"),
    ("Size", "Size:"),
    ("Gender", "Gender:"),
)


def create_retry_session(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> requests.Session:
    """Create a requests Session configured with HTTPAdapter exponential retries.

    Args:
        max_retries: Maximum number of retry attempts for transient HTTP failures.
        backoff_factor: Exponential backoff multiplier applied between retries.

    Returns:
        A configured ``requests.Session`` instance.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative.")
    if backoff_factor < 0:
        raise ValueError("backoff_factor must be non-negative.")

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _validate_scrape_args(
    base_url: str,
    max_pages: int,
    timeout: float,
    max_retries: int,
    backoff_factor: float,
) -> str:
    """Validate extraction inputs upfront using explicit guard clauses."""
    cleaned_url = base_url.strip().rstrip("/")
    parsed = urlparse(cleaned_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be a valid http:// or https:// URL.")
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1.")
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0.")
    if max_retries < 0:
        raise ValueError("max_retries must be non-negative.")
    if backoff_factor < 0:
        raise ValueError("backoff_factor must be non-negative.")
    return cleaned_url


def _build_page_url(base_url: str, page: int) -> str:
    """Build the paginated catalog URL for a given 1-based page index."""
    if page == 1:
        return f"{base_url}/"
    return f"{base_url}/page{page}/"


def _match_detail_field(text: str) -> Optional[tuple[str, str]]:
    """Match a product detail paragraph against known attribute markers."""
    for field_name, marker in DETAIL_FIELD_MARKERS:
        if marker in text:
            return field_name, text
    return None


def _extract_card_details(card: Tag) -> dict[str, Optional[str]]:
    """Extract Rating, Colors, Size, and Gender fields from a card element."""
    fields: dict[str, Optional[str]] = {
        "Rating": None,
        "Colors": None,
        "Size": None,
        "Gender": None,
    }
    for detail in card.find_all("p"):
        matched = _match_detail_field(detail.text.strip())
        if matched is not None:
            field_name, value = matched
            fields[field_name] = value
    return fields


def _parse_product_card(card: Tag) -> dict[str, Optional[str]]:
    """Parse a single HTML collection-card node into a flat product dictionary."""
    title_elem = card.find("h3", class_="product-title")
    price_elem = card.find(class_="price")
    details = _extract_card_details(card)
    return {
        "Title": title_elem.text.strip() if title_elem else None,
        "Price": price_elem.text.strip() if price_elem else None,
        "Rating": details["Rating"],
        "Colors": details["Colors"],
        "Size": details["Size"],
        "Gender": details["Gender"],
    }


def _parse_page_html(html_content: bytes) -> list[dict[str, Optional[str]]]:
    """Parse all product collection cards from a raw HTML response body."""
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", class_="collection-card")
    return [_parse_product_card(card) for card in cards]


def _execute_get(
    url: str,
    timeout: float,
    session: Optional[requests.Session],
) -> bytes:
    """Execute a single HTTP GET request with explicit timeout enforcement."""
    # Calling requests.get directly when no session is injected preserves mock compatibility.
    response = (
        session.get(url, timeout=timeout)
        if session is not None
        else requests.get(url, timeout=timeout)
    )
    response.raise_for_status()
    return response.content


def _sleep_exponential_backoff(attempt: int, backoff_factor: float) -> None:
    """Sleep with exponential backoff between retry attempts when configured."""
    delay = backoff_factor * (2**attempt)
    if delay > 0:
        time.sleep(delay)


def _fetch_page_with_retry(
    url: str,
    page: int,
    timeout: float,
    max_retries: int,
    backoff_factor: float,
    session: Optional[requests.Session] = None,
) -> Optional[bytes]:
    """Fetch a catalog page using bounded retries with exponential backoff."""
    total_attempts = max_retries + 1
    for attempt in range(total_attempts):
        try:
            return _execute_get(url, timeout=timeout, session=session)
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "HTTP error fetching page=%d attempt=%d/%d: %s",
                page,
                attempt + 1,
                total_attempts,
                exc,
            )
            if attempt < max_retries:
                _sleep_exponential_backoff(attempt, backoff_factor)

    logger.error("Exhausted %d attempts fetching page=%d url=%s", total_attempts, page, url)
    return None


def scrape_fashion_data(
    base_url: str = DEFAULT_BASE_URL,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """Extract fashion product catalog records across paginated HTML listings.

    Args:
        base_url: Base HTTP(S) URL of the Fashion Studio storefront.
        max_pages: Number of catalog pages to scrape sequentially.
        timeout: Per-request HTTP timeout in seconds.
        max_retries: Maximum retry attempts on transient ``RequestException`` errors.
        backoff_factor: Base delay multiplier in seconds for exponential backoff.
        session: Optional pre-configured ``requests.Session`` for connection pooling.

    Returns:
        DataFrame containing raw extracted product records.

    Raises:
        ValueError: If any numeric parameter or ``base_url`` is invalid.
    """
    cleaned_base_url = _validate_scrape_args(
        base_url=base_url,
        max_pages=max_pages,
        timeout=timeout,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
    )
    logger.info("Starting extraction from %s (max_pages=%d)", cleaned_base_url, max_pages)

    records: list[dict[str, Optional[str]]] = []
    for page in range(1, max_pages + 1):
        url = _build_page_url(cleaned_base_url, page)
        html_content = _fetch_page_with_retry(
            url=url,
            page=page,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            session=session,
        )
        if html_content is not None:
            records.extend(_parse_page_html(html_content))

    logger.info("Extraction finished: collected %d raw product records", len(records))
    return pd.DataFrame(records)
