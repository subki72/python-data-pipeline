"""Unit tests for the transform stage schema validation and normalization."""

from __future__ import annotations

import unittest

import pandas as pd

from src.transform import clean_data, validate_raw_dataframe


class TestTransform(unittest.TestCase):
    """Tests verifying filtering, deduplication, currency conversion, and error guards."""

    def test_clean_data_success(self) -> None:
        """Should remove sentinel invalid records and normalize types cleanly."""
        # Arrange
        raw_data = {
            "Title": ["Shirt A", "Unknown Product", "Pants B"],
            "Price": ["$10.00", "$20.00", "Price Unavailable"],
            "Rating": ["Rating: 4.5 / 5", "Invalid Rating", "Rating: 5.0 / 5"],
            "Colors": ["3 Colors", "2 Colors", "1 Colors"],
            "Size": ["Size: M", "Size: L", "Size: S"],
            "Gender": ["Gender: Men", "Gender: Women", "Gender: Unisex"],
        }
        df_raw = pd.DataFrame(raw_data)

        # Act
        df_clean = clean_data(df_raw)

        # Assert
        self.assertIsNotNone(df_clean)
        assert df_clean is not None
        self.assertEqual(len(df_clean), 1)
        self.assertEqual(df_clean.iloc[0]["Title"], "Shirt A")
        self.assertEqual(df_clean.iloc[0]["Price"], 160000.0)
        self.assertEqual(df_clean.iloc[0]["Rating"], 4.5)
        self.assertEqual(df_clean.iloc[0]["Colors"], 3)
        self.assertEqual(df_clean.iloc[0]["Size"], "M")
        self.assertEqual(df_clean.iloc[0]["Gender"], "Men")
        self.assertIn("timestamp", df_clean.columns)

    def test_clean_data_deduplicates_and_handles_integer_ratings(self) -> None:
        """Should deduplicate identical rows and parse comma prices and integer ratings."""
        # Arrange
        raw_data = {
            "Title": ["Jacket X", "Jacket X"],
            "Price": ["$1,000.00", "$1,000.00"],
            "Rating": ["Rating: 5 / 5", "Rating: 5 / 5"],
            "Colors": ["4 Colors", "4 Colors"],
            "Size": ["Size: XL", "Size: XL"],
            "Gender": ["Gender: Unisex", "Gender: Unisex"],
        }

        # Act
        df_clean = clean_data(pd.DataFrame(raw_data))

        # Assert
        self.assertIsNotNone(df_clean)
        assert df_clean is not None
        self.assertEqual(len(df_clean), 1)
        self.assertEqual(df_clean.iloc[0]["Price"], 16000000.0)
        self.assertEqual(df_clean.iloc[0]["Rating"], 5.0)

    def test_clean_data_returns_none_on_invalid_input(self) -> None:
        """Should return None when given None, empty DataFrame, or missing columns."""
        self.assertIsNone(clean_data(None))
        self.assertIsNone(clean_data(pd.DataFrame()))
        self.assertIsNone(clean_data(pd.DataFrame({"Title": ["Only Title"]})))

    def test_clean_data_returns_none_on_non_positive_exchange_rate(self) -> None:
        """Should reject non-positive USD-to-IDR exchange rates."""
        df = pd.DataFrame(
            {
                "Title": ["Shirt A"],
                "Price": ["$10.00"],
                "Rating": ["Rating: 4.5 / 5"],
                "Colors": ["3 Colors"],
                "Size": ["Size: M"],
                "Gender": ["Gender: Men"],
            }
        )
        self.assertIsNone(clean_data(df, exchange_rate=0.0))

    def test_validate_raw_dataframe_raises_on_missing_columns(self) -> None:
        """Should raise ValueError listing missing required columns."""
        with self.assertRaises(ValueError):
            validate_raw_dataframe(pd.DataFrame({"Title": ["Item"]}))


if __name__ == "__main__":
    unittest.main()
