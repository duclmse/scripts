"""Structured JSON logging with a per-invocation correlation ID."""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

# Attributes that belong to LogRecord internals, not our structured payload.
_SKIP: frozenset[str] = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs",
    "msg", "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
})

# Single correlation ID shared across the whole process invocation.
CORRELATION_ID: str = str(uuid.uuid4())[:8]


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "cid": CORRELATION_ID,
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        # Attach any extra={} fields the caller injected.
        for k, v in record.__dict__.items():
            if k not in _SKIP and not k.startswith("_"):
                data[k] = v
        return json.dumps(data, default=str)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return (or create) a named JSON logger scoped under *aws.*."""
    full = f"aws.{name}"
    logger = logging.getLogger(full)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def set_level(level: str) -> None:
    """Update every active aws.* logger to *level* (called after CLI parses --log-level)."""
    lvl = getattr(logging, level.upper(), logging.INFO)
    mgr = logging.Logger.manager
    for name, obj in mgr.loggerDict.items():
        if name.startswith("aws.") and isinstance(obj, logging.Logger):
            obj.setLevel(lvl)
            for h in obj.handlers:
                h.setLevel(lvl)
