"""Structured (JSON lines) logging with request correlation.

Design rules:
- One JSON object per line so logs can be shipped to any aggregator later.
- The current ``request_id`` is read from a ``ContextVar`` and stamped on every record,
  so any module can just ``logger.info(...)`` and still be correlated.
- Call sites pass structured fields via ``extra={...}``; they are merged into the JSON.
- Privacy: nothing here logs message bodies. Callers log lengths and timings, not content.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes present on every LogRecord; anything else came from ``extra``.
_STANDARD_ATTRS = frozenset(
    vars(logging.makeLogRecord({})).keys() | {"message", "asctime", "taskName"}
)

# Keys that must never appear in logs even if a caller passes them by mistake.
_REDACTED_KEYS = frozenset({"api_key", "authorization", "password", "secret", "token"})


def get_request_id() -> str | None:
    return request_id_var.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = "[REDACTED]" if key.lower() in _REDACTED_KEYS else value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Uvicorn installs its own handlers; route them through ours for consistent output.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
