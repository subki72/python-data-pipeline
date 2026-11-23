"""Unit tests for the load stage sinks (CSV, Google Sheets, and PostgreSQL)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from gspread.exceptions import GSpreadException
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from src.load import (
    save_to_csv,
    save_to_google_sheets,
    save_to_postgresql,
    validate_db_url,
    validate_table_name,
)


class TestLoad(unittest.TestCase):
    """Tests covering load sinks, input guards, and error handling."""

    @patch("pandas.DataFrame.to_csv")
    def test_save_to_csv_success(self, mock_to_csv: Mock) -> None:
        """Should persist DataFrame to CSV without row index."""
        df = pd.DataFrame({"Title": ["A"], "Price": [100]})
        result = save_to_csv(df, "dummy.csv")
        self.assertTrue(result)
        mock_to_csv.assert_called_once_with("dummy.csv", index=False)

    def test_save_to_csv_creates_nested_directory(self) -> None:
        """Should create missing parent directories and write real CSV content."""
        df = pd.DataFrame({"Title": ["Coat"], "Price": [320000.0]})
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = Path(tmp_dir) / "nested" / "products.csv"
            result = save_to_csv(df, output_file)
            self.assertTrue(result)
            self.assertTrue(output_file.is_file())

    def test_save_to_csv_empty(self) -> None:
        """Should skip writing and return False for empty DataFrames."""
        df = pd.DataFrame()
        result = save_to_csv(df, "dummy.csv")
        self.assertFalse(result)

    @patch("pandas.DataFrame.to_csv", side_effect=OSError("disk full"))
    def test_save_to_csv_handles_os_error(self, _mock_to_csv: Mock) -> None:
        """Should return False gracefully when CSV write raises OSError."""
        df = pd.DataFrame({"Title": ["A"], "Price": [100]})
        self.assertFalse(save_to_csv(df, "dummy.csv"))

    @patch("src.load.Credentials.from_service_account_file")
    @patch("src.load.gspread.authorize")
    def test_save_to_google_sheets_success(
        self,
        mock_authorize: Mock,
        _mock_credentials: Mock,
    ) -> None:
        """Should clear worksheet and upload header plus row values."""
        df = pd.DataFrame({"Title": ["Hat"], "Price": [50000]})
        mock_client = mock_authorize.return_value
        mock_sheet = mock_client.open.return_value.sheet1

        result = save_to_google_sheets(df, "dummy.json", "Dummy_Sheet")

        self.assertTrue(result)
        mock_sheet.clear.assert_called_once()
        mock_sheet.update.assert_called_once()

    @patch(
        "src.load.Credentials.from_service_account_file",
        side_effect=GSpreadException("quota exceeded"),
    )
    def test_save_to_google_sheets_handles_api_error(self, _mock_creds: Mock) -> None:
        """Should return False gracefully on Google Sheets API failure."""
        df = pd.DataFrame({"Title": ["Hat"], "Price": [50000]})
        self.assertFalse(save_to_google_sheets(df, "dummy.json", "Dummy_Sheet"))

    @patch("pandas.DataFrame.to_sql")
    @patch("src.load.create_engine")
    def test_save_to_postgresql_success(
        self,
        mock_create_engine: Mock,
        mock_to_sql: Mock,
    ) -> None:
        """Should write rows to PostgreSQL and dispose the SQLAlchemy engine."""
        df = pd.DataFrame({"Title": ["Shirt"], "Price": [100000]})
        mock_engine = mock_create_engine.return_value

        result = save_to_postgresql(
            df,
            "postgresql://dummy:dummy@localhost/db",
            "test_table",
        )

        self.assertTrue(result)
        mock_to_sql.assert_called_once_with(
            "test_table",
            mock_engine,
            if_exists="replace",
            index=False,
        )
        mock_engine.dispose.assert_called_once()

    @patch("src.load.create_engine", side_effect=SQLAlchemyError("connection refused"))
    def test_save_to_postgresql_handles_db_error(self, _mock_engine: Mock) -> None:
        """Should catch SQLAlchemyError and return False."""
        df = pd.DataFrame({"Title": ["Shirt"], "Price": [100000]})
        result = save_to_postgresql(
            df,
            "postgresql://dummy:dummy@localhost/db",
            "test_table",
        )
        self.assertFalse(result)

    def test_save_to_postgresql_rejects_unsafe_table_and_scheme(self) -> None:
        """Should reject SQL injection payloads in table names and invalid DB URLs."""
        df = pd.DataFrame({"Title": ["Shirt"], "Price": [100000]})
        self.assertFalse(
            save_to_postgresql(df, "postgresql://dummy:dummy@localhost/db", "users; DROP TABLE x")
        )
        self.assertFalse(save_to_postgresql(df, "mysql://dummy:dummy@localhost/db", "valid_table"))

    def test_validators_enforce_safe_identifiers_and_schemes(self) -> None:
        """Should validate safe table identifiers and allowed database schemes."""
        self.assertEqual(validate_table_name("fashion_products"), "fashion_products")
        self.assertEqual(
            validate_db_url("postgresql://dummy:dummy@localhost/db"),
            "postgresql://dummy:dummy@localhost/db",
        )
        with self.assertRaises(ValueError):
            validate_table_name("123-invalid")
        with self.assertRaises(ValueError):
            validate_db_url("")


if __name__ == "__main__":
    unittest.main()
