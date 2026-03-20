"""
Centralised logging setup.

Usage
-----
# In application startup (main.py):
    from app.core.logging_config import logging_manager
    logging_manager.setup()

# In any module:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)

Extending with a third-party sink
----------------------------------
Subclass LogSink and register it after setup():

    from app.core.logging_config import LogSink, logging_manager

    class DatadogSink(LogSink):
        def emit(self, record: logging.LogRecord) -> None:
            # forward to Datadog, Sentry, Logtail, etc.
            ...

    logging_manager.add_sink(DatadogSink())

The sink receives every log record *in addition to* the terminal output.
"""

import json
import logging
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Public ABC — implement this to add a third-party sink
# ---------------------------------------------------------------------------

class LogSink(ABC):
    """
    Pluggable log sink.

    Implement :meth:`emit` to forward records to any external logging platform.
    The terminal handler is always active; sinks are *additional* destinations.
    """

    @abstractmethod
    def emit(self, record: logging.LogRecord) -> None:
        """Receive a log record and forward it to the target platform."""
        ...


# ---------------------------------------------------------------------------
# Internal bridge — wraps a LogSink as a standard logging.Handler
# ---------------------------------------------------------------------------

class _SinkHandler(logging.Handler):
    """Bridges Python's logging machinery to a :class:`LogSink`."""

    def __init__(self, sink: LogSink) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._sink.emit(record)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class _TextFormatter(logging.Formatter):
    _LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[1;31m", # bold red
    }
    _RESET = "\033[0m"

    def __init__(self, colorize: bool = True) -> None:
        super().__init__()
        self._colorize = colorize

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = self._LEVEL_COLORS.get(level, "") if self._colorize else ""
        reset = self._RESET if self._colorize else ""
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        base = f"{ts} {color}{level:<8}{reset} {record.name} - {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class _JsonFormatter(logging.Formatter):
    """Structured JSON output — suitable for log aggregation platforms."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts":      datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        # Carry any extra fields attached via logger.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class LoggingManager:
    """
    Singleton that owns the root logger configuration.

    - Terminal (stderr) output is always active.
    - Additional sinks can be registered with :meth:`add_sink`.
    - Call :meth:`setup` once at application startup.
    """

    def __init__(self) -> None:
        self._configured = False
        self._level = logging.INFO

    def setup(
        self,
        level: str = "INFO",
        json_format: bool = False,
        colorize: bool = True,
    ) -> None:
        """
        Configure the root logger.

        Parameters
        ----------
        level:
            Minimum log level (DEBUG / INFO / WARNING / ERROR / CRITICAL).
        json_format:
            Emit JSON lines instead of human-readable text.
            Recommended in production / containerised environments.
        colorize:
            Add ANSI colour codes to the text formatter.
            Automatically disabled when stdout is not a TTY.
        """
        self._level = getattr(logging, level.upper(), logging.INFO)

        root = logging.getLogger()
        root.setLevel(self._level)
        root.handlers.clear()

        # --- terminal handler (always present) ---
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(self._level)
        if json_format:
            console.setFormatter(_JsonFormatter())
        else:
            tty_colorize = colorize and sys.stderr.isatty()
            console.setFormatter(_TextFormatter(colorize=tty_colorize))
        root.addHandler(console)

        # --- quieten noisy third-party loggers ---
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

        self._configured = True
        logging.getLogger(__name__).debug("Logging initialised — level=%s json=%s", level, json_format)

    def add_sink(self, sink: LogSink) -> None:
        """
        Register an additional log sink.

        Can be called any time after :meth:`setup`.  Logs are forwarded to the
        sink *in addition to* the terminal; the terminal handler is never removed.

        Parameters
        ----------
        sink:
            A :class:`LogSink` implementation that forwards records to an
            external platform (Sentry, Datadog, Logtail, Grafana Loki, …).
        """
        if not self._configured:
            raise RuntimeError("Call logging_manager.setup() before registering sinks.")
        handler = _SinkHandler(sink)
        handler.setLevel(self._level)
        logging.getLogger().addHandler(handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Return a named logger (thin wrapper around ``logging.getLogger``)."""
        return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Module-level singleton and convenience function
# ---------------------------------------------------------------------------

logging_manager = LoggingManager()


def get_logger(name: str) -> logging.Logger:
    """
    Drop-in replacement for ``logging.getLogger()``.

    Prefer this over importing ``logging`` directly so all loggers in the
    application flow through the centralised :data:`logging_manager`.

    Usage::

        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
    """
    return logging_manager.get_logger(name)
