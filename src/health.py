"""Operational observability: structured logging, health checks, and error boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Any, Iterator, Optional

from src.config import ConfigValidationError, PipelineConfig

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
HEALTH_ENDPOINT = "/health"


def configure_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured leveled logging for the pipeline process.

    Avoids duplicating stream handlers if logging is already initialized.

    Args:
        log_level: Standard Python logging level name (e.g. ``"INFO"``).

    Returns:
        The configured root ``logging.Logger`` instance.
    """
    normalized = log_level.strip().upper()
    numeric_level = getattr(logging, normalized, logging.INFO)
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(level=numeric_level, format=LOG_FORMAT)
    else:
        root_logger.setLevel(numeric_level)

    logger.info("Structured logging configured at level=%s", logging.getLevelName(numeric_level))
    return root_logger


@dataclass(frozen=True)
class ErrorRecord:
    """Immutable structured representation of a captured pipeline error."""

    stage: str
    error_type: str
    message: str
    timestamp: str
    recoverable: bool


class PipelineErrorHandler:
    """Centralized exception boundary for ETL pipeline stages.

    Records structured error telemetry while allowing recoverable sink
    failures to be isolated from critical extract/transform stages.
    """

    def __init__(self) -> None:
        self._records: list[ErrorRecord] = []

    @property
    def records(self) -> tuple[ErrorRecord, ...]:
        """Return all captured error records in chronological order."""
        return tuple(self._records)

    @property
    def has_errors(self) -> bool:
        """Return True if at least one error has been recorded."""
        return bool(self._records)

    def handle_exception(
        self,
        stage: str,
        exc: Exception,
        *,
        recoverable: bool = True,
    ) -> ErrorRecord:
        """Log and record an exception raised within a named pipeline stage.

        Args:
            stage: Logical pipeline stage identifier (e.g. ``"load:postgres"``).
            exc: Caught exception instance.
            recoverable: Whether execution may safely proceed to subsequent stages.

        Returns:
            The persisted ``ErrorRecord`` instance.
        """
        record = ErrorRecord(
            stage=stage,
            error_type=type(exc).__name__,
            message=str(exc),
            timestamp=datetime.now(timezone.utc).isoformat(),
            recoverable=recoverable,
        )
        self._records.append(record)
        log_fn = logger.warning if recoverable else logger.error
        log_fn(
            "Pipeline error captured in stage=%s type=%s recoverable=%s detail=%s",
            record.stage,
            record.error_type,
            record.recoverable,
            record.message,
        )
        return record

    @contextmanager
    def capture(self, stage: str, *, reraise: bool = False) -> Iterator[None]:
        """Context manager wrapping a pipeline stage in centralized error handling.

        Args:
            stage: Logical stage name for structured logging.
            reraise: If True, re-raises the exception after recording it.
        """
        try:
            yield
        except Exception as exc:
            self.handle_exception(stage, exc, recoverable=not reraise)
            if reraise:
                raise

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable summary of captured errors."""
        return {
            "error_count": len(self._records),
            "has_fatal_error": any(not item.recoverable for item in self._records),
            "errors": [asdict(item) for item in self._records],
        }


def _check_output_directory(output_csv_path: str) -> dict[str, Any]:
    """Verify the CSV output parent directory is accessible and writable."""
    target_dir = Path(output_csv_path).parent
    resolved_dir = target_dir if str(target_dir) not in ("", ".") else Path.cwd()
    probe_dir = resolved_dir if resolved_dir.exists() else resolved_dir.parent
    is_writable = probe_dir.exists() and os.access(probe_dir, os.W_OK)
    return {
        "ok": is_writable,
        "path": str(resolved_dir),
    }


def _evaluate_health_status(checks: dict[str, dict[str, Any]]) -> str:
    """Derive overall /health readiness status from individual subsystem probes."""
    if not checks["config"]["ok"] or not checks["output_directory"]["ok"]:
        return "unhealthy"
    optional_ready = checks["google_credentials"]["ok"] and checks["database_config"]["ok"]
    return "healthy" if optional_ready else "degraded"


def check_pipeline_health(config: Optional[PipelineConfig] = None) -> dict[str, Any]:
    """Execute pre-flight readiness checks and return a structured /health payload.

    Args:
        config: Optional pre-loaded ``PipelineConfig``; loads from env when omitted.

    Returns:
        Dictionary adhering to the ``/health`` readiness contract.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        active_config = config if config is not None else PipelineConfig.from_env()
        active_config.validate()
    except ConfigValidationError as exc:
        logger.error("Health check failed during config validation: %s", exc)
        return {
            "endpoint": HEALTH_ENDPOINT,
            "status": "unhealthy",
            "timestamp": timestamp,
            "checks": {
                "config": {"ok": False, "detail": str(exc)},
                "output_directory": {"ok": False, "path": ""},
                "google_credentials": {"ok": False, "path": ""},
                "database_config": {"ok": False, "configured": False},
            },
        }

    creds_path = Path(active_config.google_creds_path)
    checks: dict[str, dict[str, Any]] = {
        "config": {"ok": True, "detail": "Configuration validated"},
        "output_directory": _check_output_directory(active_config.output_csv_path),
        "google_credentials": {"ok": creds_path.is_file(), "path": str(creds_path)},
        "database_config": {
            "ok": bool(active_config.db_url),
            "configured": bool(active_config.db_url),
            "target": active_config.masked_db_url(),
        },
    }
    status = _evaluate_health_status(checks)
    logger.info("Pre-flight %s check completed with status=%s", HEALTH_ENDPOINT, status)
    return {
        "endpoint": HEALTH_ENDPOINT,
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
    }
