"""Unit tests for the extract stage web scraping and retry behavior."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from src.extract import create_retry_session, scrape_fashion_data

SAMPLE_PRODUCT_HTML = """
<html><body>
    <div class="collection-card">
        <h3 class="product-title">Cool Shirt</h3>
        <p class="price">$10.00</p>
        <p>Rating: 4.5 / 5</p>
        <p>3 Colors</p>
        <p>Size: M</p>
        <p>Gender: Men</p>
    </div>
</body></html>
"""


class TestExtract(unittest.TestCase):
    """Tests covering catalog extraction, validation, and retry resilience."""

    @patch("src.extract.requests.get")
    def test_scrape_fashion_data_success(self, mock_get: Mock) -> None:
        """Should parse product card attributes on HTTP 200 response."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = SAMPLE_PRODUCT_HTML.encode("utf-8")
        mock_get.return_value = mock_response

        # Act
        result_df = scrape_fashion_data(max_pages=1)

        # Assert
        self.assertFalse(result_df.empty)
        self.assertEqual(len(result_df), 1)
        self.assertEqual(result_df.iloc[0]["Title"], "Cool Shirt")
        self.assertEqual(result_df.iloc[0]["Price"], "$10.00")
        self.assertEqual(result_df.iloc[0]["Size"], "Size: M")

    @patch("src.extract.time.sleep")
    @patch("src.extract.requests.get")
    def test_scrape_fashion_data_recovers_after_transient_error(
        self,
        mock_get: Mock,
        mock_sleep: Mock,
    ) -> None:
        """Should retry with exponential backoff and recover on subsequent success."""
        # Arrange
        success_response = Mock()
        success_response.status_code = 200
        success_response.content = SAMPLE_PRODUCT_HTML.encode("utf-8")
        mock_get.side_effect = [
            requests.exceptions.Timeout("transient timeout"),
            success_response,
        ]

        # Act
        result_df = scrape_fashion_data(max_pages=1, max_retries=2, backoff_factor=0.25)

        # Assert
        self.assertEqual(len(result_df), 1)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(0.25)

    @patch("src.extract.time.sleep")
    @patch("src.extract.requests.get")
    def test_scrape_fashion_data_returns_empty_when_retries_exhausted(
        self,
        mock_get: Mock,
        mock_sleep: Mock,
    ) -> None:
        """Should return an empty DataFrame after exhausting all retry attempts."""
        # Arrange
        mock_get.side_effect = requests.exceptions.ConnectionError("unreachable")

        # Act
        result_df = scrape_fashion_data(max_pages=1, max_retries=2, backoff_factor=0.1)

        # Assert
        self.assertTrue(result_df.empty)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("src.extract.requests.get")
    def test_scrape_fashion_data_paginated_urls(self, mock_get: Mock) -> None:
        """Should request root path for page 1 and /pageN/ for subsequent pages."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = SAMPLE_PRODUCT_HTML.encode("utf-8")
        mock_get.return_value = mock_response

        # Act
        result_df = scrape_fashion_data(base_url="https://example.test", max_pages=2)

        # Assert
        self.assertEqual(len(result_df), 2)
        called_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertEqual(called_urls, ["https://example.test/", "https://example.test/page2/"])

    def test_scrape_fashion_data_invalid_args_raises(self) -> None:
        """Should raise ValueError when base_url or pagination bounds are invalid."""
        with self.assertRaises(ValueError):
            scrape_fashion_data(base_url="ftp://invalid.example", max_pages=1)
        with self.assertRaises(ValueError):
            scrape_fashion_data(max_pages=0)
        with self.assertRaises(ValueError):
            scrape_fashion_data(timeout=0)

    def test_create_retry_session_mounts_http_adapters(self) -> None:
        """Should mount HTTPAdapter with Retry configuration on HTTP and HTTPS."""
        # Act
        session = create_retry_session(max_retries=2, backoff_factor=0.5)

        # Assert
        try:
            https_adapter = session.get_adapter("https://example.test")
            self.assertEqual(https_adapter.max_retries.total, 2)
            self.assertEqual(https_adapter.max_retries.backoff_factor, 0.5)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
