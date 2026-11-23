"""Integration tests covering end-to-end ETL execution, health checks, and resilience."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

import main as pipeline_main
from src.config import PipelineConfig
from src.health import PipelineErrorHandler, check_pipeline_health, configure_logging

INTEGRATION_HTML = """
<html><body>
    <div class="collection-card">
        <h3 class="product-title">Linen Jacket</h3>
        <p class="price">$25.50</p>
        <p>Rating: 4.8 / 5</p>
        <p>4 Colors</p>
        <p>Size: L</p>
        <p>Gender: Women</p>
    </div>
    <div class="collection-card">
        <h3 class="product-title">Unknown Product</h3>
        <p class="price">$12.00</p>
        <p>Rating: Invalid Rating</p>
        <p>2 Colors</p>
        <p>Size: S</p>
        <p>Gender: Men</p>
    </div>
</body></html>
"""


def _make_integration_config(tmp_dir: str) -> tuple[PipelineConfig, Path]:
    """Create a temporary integration PipelineConfig with dummy credential file."""
    csv_path = Path(tmp_dir) / "data" / "products.csv"
    creds_file = Path(tmp_dir) / "dummy-creds.json"
    creds_file.write_text("{}", encoding="utf-8")
    config = PipelineConfig(
        base_url="https://catalog.example.test",
        max_pages=1,
        output_csv_path=str(csv_path),
        google_creds_path=str(creds_file),
        spreadsheet_name="Integration-Sheet",
        db_url="postgresql://dummy:dummy@localhost:5432/test_db",
        db_table="fashion_products",
        request_timeout=5.0,
        max_retries=2,
        retry_backoff_factor=0.1,
        log_level="INFO",
    )
    return config, csv_path


class TestPipelineIntegration(unittest.TestCase):
    """End-to-end integration tests for the orchestrated ETL workflow."""

    @patch("main.save_to_postgresql", return_value=True)
    @patch("main.save_to_google_sheets", return_value=True)
    @patch("src.extract.time.sleep")
    @patch("src.extract.requests.get")
    def test_run_pipeline_end_to_end_with_retry_and_csv_output(
        self,
        mock_get: Mock,
        mock_sleep: Mock,
        mock_sheets: Mock,
        mock_postgres: Mock,
    ) -> None:
        """Should extract with retry recovery, clean records, and load to all sinks."""
        # Arrange
        ok_response = Mock(status_code=200, content=INTEGRATION_HTML.encode("utf-8"))
        mock_get.side_effect = [requests.exceptions.Timeout("transient timeout"), ok_response]

        with tempfile.TemporaryDirectory() as tmp_dir:
            config, csv_path = _make_integration_config(tmp_dir)

            # Act
            summary = pipeline_main.run_pipeline(config=config)

            # Assert
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["extracted_rows"], 2)
            self.assertEqual(summary["cleaned_rows"], 1)
            self.assertEqual(summary["sinks"], {"csv": True, "google_sheets": True, "postgresql": True})
            self.assertEqual(summary["health"]["status"], "healthy")
            self.assertEqual(summary["errors"]["error_count"], 0)
            mock_sleep.assert_called_once_with(0.1)
            mock_sheets.assert_called_once()
            mock_postgres.assert_called_once()

            written_df = pd.read_csv(csv_path)
            self.assertEqual(len(written_df), 1)
            self.assertEqual(written_df.iloc[0]["Title"], "Linen Jacket")
            self.assertEqual(written_df.iloc[0]["Price"], 408000.0)
            self.assertEqual(written_df.iloc[0]["Size"], "L")

    @patch("src.extract.requests.get")
    def test_run_pipeline_stops_cleanly_when_no_valid_rows(self, mock_get: Mock) -> None:
        """Should halt before load sinks when extraction yields zero clean records."""
        # Arrange
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.content = b"<html><body></body></html>"
        mock_get.return_value = empty_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = PipelineConfig(
                base_url="https://catalog.example.test",
                max_pages=1,
                output_csv_path=str(Path(tmp_dir) / "products.csv"),
                max_retries=0,
            )

            # Act
            summary = pipeline_main.run_pipeline(config=config)

            # Assert
            self.assertEqual(summary["status"], "empty")
            self.assertEqual(summary["cleaned_rows"], 0)
            self.assertFalse(summary["sinks"]["csv"])

    def test_check_pipeline_health_reports_healthy_degraded_and_unhealthy(self) -> None:
        """Should report structured /health states matching dependency readiness."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            creds_file = Path(tmp_dir) / "dummy-creds.json"
            creds_file.write_text("{}", encoding="utf-8")

            healthy_cfg = PipelineConfig(
                output_csv_path=str(Path(tmp_dir) / "products.csv"),
                google_creds_path=str(creds_file),
                db_url="postgresql://dummy:dummy@localhost:5432/test_db",
            )
            healthy = check_pipeline_health(healthy_cfg)
            self.assertEqual(healthy["endpoint"], "/health")
            self.assertEqual(healthy["status"], "healthy")

            degraded_cfg = PipelineConfig(
                output_csv_path=str(Path(tmp_dir) / "products.csv"),
                google_creds_path=str(Path(tmp_dir) / "missing.json"),
                db_url=None,
            )
            degraded = check_pipeline_health(degraded_cfg)
            self.assertEqual(degraded["status"], "degraded")

            invalid_cfg = PipelineConfig(base_url="invalid-url")
            unhealthy = check_pipeline_health(invalid_cfg)
            self.assertEqual(unhealthy["status"], "unhealthy")

    def test_error_handler_captures_recoverable_and_reraises_fatal(self) -> None:
        """Should record recoverable stage failures and propagate fatal ones."""
        configure_logging("INFO")
        handler = PipelineErrorHandler()

        with handler.capture("load:google_sheets", reraise=False):
            raise RuntimeError("temporary sheets outage")

        self.assertTrue(handler.has_errors)
        self.assertFalse(handler.summary()["has_fatal_error"])

        with self.assertRaises(ValueError):
            with handler.capture("extract", reraise=True):
                raise ValueError("fatal extraction contract violation")

        summary = handler.summary()
        self.assertEqual(summary["error_count"], 2)
        self.assertTrue(summary["has_fatal_error"])

    @patch("sys.stdout.write")
    def test_cli_health_flag_outputs_valid_json(self, mock_write: Mock) -> None:
        """Should output JSON /health readiness report and return exit code 0."""
        exit_code = pipeline_main.main(["--health"])

        self.assertEqual(exit_code, 0)
        mock_write.assert_called_once()
        payload = json.loads(mock_write.call_args.args[0])
        self.assertEqual(payload["endpoint"], "/health")
        self.assertIn(payload["status"], {"healthy", "degraded"})


if __name__ == "__main__":
    unittest.main()
