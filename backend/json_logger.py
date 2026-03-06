"""
json_logger.py  –  Structured JSON logging for production.
Replaces plain-text logs with machine-parsable JSON output.
"""

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

# ── Context variables for request tracking ────────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

SERVICE_NAME = os.getenv("SERVICE_NAME", "iot-healthcare")


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": SERVICE_NAME,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }

        # Add user_id if available
        uid = user_id_var.get(None)
        if uid is not None:
            log_entry["user_id"] = uid

        # Add action if set as extra
        if hasattr(record, "action"):
            log_entry["action"] = record.action

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        # Add exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = None):
    """Configure root logger with JSON formatting."""
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    # Remove existing handlers
    root = logging.getLogger()
    root.handlers.clear()

    # Create JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Reduce noise from third-party libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:12]
