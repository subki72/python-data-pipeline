"""Unit tests for validated environment-backed PipelineConfig."""

from __future__ import annotations

import unittest

from src.config import ConfigValidationError, PipelineConfig


class TestPipelineConfig(unittest.TestCase):
    """Tests covering configuration loading, validation, and secret redaction."""

    def test_from_env_uses_safe_defaults(self) -> None:
        """Should load valid default settings when environment is empty."""
        # Act
        config = PipelineConfig.from_env(env={})

        # Assert
        self.assertEqual(config.base_url, "https://fashion-studio.dicoding.dev")
        self.assertEqual(config.max_pages, 50)
        self.assertEqual(config.output_csv_path, "data/products.csv")
        self.assertEqual(config.db_table, "fashion_products")
        self.assertIsNone(config.db_url)
        self.assertEqual(config.request_timeout, 10.0)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.log_level, "INFO")

    def test_from_env_parses_custom_overrides(self) -> None:
        """Should parse and normalize custom environment variable values."""
        # Arrange
        custom_env = {
            "BASE_URL": "https://catalog.example.test/",
            "MAX_PAGES": "12",
            "OUTPUT_CSV_PATH": "out/custom.csv",
            "GOOGLE_CREDS_PATH": "credentials/mock-key.json",
            "SPREADSHEET_NAME": "Custom-Sheet",
            "DB_URL": "postgresql://dummy_user:dummy_pass@localhost:5432/etl_test",
            "DB_TABLE": "clean_products",
            "REQUEST_TIMEOUT": "15.5",
            "MAX_RETRIES": "4",
            "RETRY_BACKOFF_FACTOR": "0.2",
            "LOG_LEVEL": "debug",
        }

        # Act
        config = PipelineConfig.from_env(env=custom_env)

        # Assert
        self.assertEqual(config.base_url, "https://catalog.example.test")
        self.assertEqual(config.max_pages, 12)
        self.assertEqual(config.output_csv_path, "out/custom.csv")
        self.assertEqual(config.db_table, "clean_products")
        self.assertEqual(config.request_timeout, 15.5)
        self.assertEqual(config.max_retries, 4)
        self.assertEqual(config.log_level, "DEBUG")

    def test_validate_rejects_invalid_url_and_bounds(self) -> None:
        """Should fail fast with ConfigValidationError on unsafe or out-of-range inputs."""
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"BASE_URL": "ftp://invalid.example"})
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"MAX_PAGES": "0"})
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"MAX_PAGES": "not-an-int"})
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"REQUEST_TIMEOUT": "-5"})
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"LOG_LEVEL": "VERBOSE"})

    def test_validate_rejects_unsafe_db_settings(self) -> None:
        """Should reject SQL injection table names and unsupported DB URL schemes."""
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"DB_TABLE": "products; DROP TABLE users"})
        with self.assertRaises(ConfigValidationError):
            PipelineConfig.from_env(env={"DB_URL": "mysql://dummy:dummy@localhost/test"})

    def test_masked_db_url_redacts_credentials(self) -> None:
        """Should mask user and password while preserving scheme, host, and database."""
        config = PipelineConfig.from_env(
            env={"DB_URL": "postgresql://dummy_user:dummy_pass@localhost:5432/fashion_etl"}
        )
        masked = config.masked_db_url()

        self.assertNotIn("dummy_pass", masked)
        self.assertNotIn("dummy_user", masked)
        self.assertEqual(masked, "postgresql://***@localhost:5432/fashion_etl")
        self.assertEqual(PipelineConfig.from_env(env={}).masked_db_url(), "<unset>")


if __name__ == "__main__":
    unittest.main()
