"""Structured JSON logging helpers."""

import json
import logging as standard_logging
from typing import Any

LOG_CONTEXT_FIELDS = (
    "service",
    "environment",
    "correlation_id",
    "method",
    "path",
    "status_code",
    "user_id",
    "order_id",
    "document_id",
    "payment_id",
    "notification_id",
    "step",
    "status",
)


class JsonFormatter(standard_logging.Formatter):
    """Format log records as compact JSON objects."""

    def __init__(self, service_name: str | None = None) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: standard_logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.service_name:
            payload["service"] = self.service_name

        for field in LOG_CONTEXT_FIELDS:
            if field == "service" and "service" in payload:
                continue
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_json_logging(
    service_name: str,
    level: int | str = standard_logging.INFO,
) -> standard_logging.Logger:
    """Configure and return a service logger that emits JSON records."""
    logger = standard_logging.getLogger(service_name)
    logger.setLevel(level)
    logger.propagate = False

    has_json_handler = any(
        isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers
    )
    if not has_json_handler:
        handler = standard_logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service_name=service_name))
        logger.addHandler(handler)

    return logger


def get_logger(service_name: str) -> standard_logging.Logger:
    """Return the logger for a service."""
    return standard_logging.getLogger(service_name)
