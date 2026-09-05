"""Logging setup: plain text, ``rich`` colour, or line-delimited JSON."""

from __future__ import annotations

import datetime as dt
import json
import logging
import logging.config
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from botbase.config import LogFormat

# discord.py's own loggers are chatty at INFO; keep them at WARNING by default.
_NOISY_LOGGERS = ("discord.http", "discord.gateway", "discord.client")

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter with no third-party dependency."""

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a single JSON line."""
        payload: dict[str, object] = {
            "ts": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        payload.update(record.__dict__.get("extra_fields", {}))
        return json.dumps(payload, default=str)


def _build_handler(fmt: LogFormat) -> logging.Handler:
    if fmt == "rich":
        try:
            from rich.logging import RichHandler
        except ModuleNotFoundError:
            pass
        else:
            return RichHandler(rich_tracebacks=True, show_path=False)

    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def configure_logging(level: str = "INFO", fmt: LogFormat = "text") -> None:
    """Configure the root logger. Safe to call once at process start.

    Parameters
    ----------
    level:
        Root log level name (``"DEBUG"``, ``"INFO"``, ...).
    fmt:
        ``"text"`` (default), ``"rich"`` (falls back to text if ``rich`` is not
        installed), or ``"json"``.
    """
    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)

    root.addHandler(_build_handler(fmt))
    root.setLevel(level.upper())

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
