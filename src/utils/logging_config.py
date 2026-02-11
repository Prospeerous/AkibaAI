"""
Structured logging for the pipeline.

Produces both console output and rotating JSON log files.
Every scrape/index/error event gets a structured record for monitoring.
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config.settings import LOG_DIR


class JSONFormatter(logging.Formatter):
    """Emit structured JSON log lines for machine consumption."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Merge any extra fields attached to the record
        for key in ("source_id", "document_id", "url", "metric", "value",
                     "duration_ms", "error_type", "phase"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Concise colored output for humans."""

    COLORS = {
        "DEBUG": "\033[90m",    # gray
        "INFO": "\033[36m",     # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[41m", # red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = f"{color}[{ts}] {record.levelname:<8}{self.RESET}"
        source = getattr(record, "source_id", "")
        source_str = f" [{source}]" if source else ""
        return f"{prefix}{source_str} {record.getMessage()}"


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Initialize the logging system.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Override log file name. Defaults to pipeline_YYYYMMDD.log
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("fincoach")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    # ── Console handler ────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ConsoleFormatter())
    root.addHandler(console)

    # ── Rotating JSON file handler ─────────────────────────────────────
    if log_file is None:
        log_file = f"pipeline_{datetime.now().strftime('%Y%m%d')}.jsonl"
    file_path = LOG_DIR / log_file

    file_handler = logging.handlers.RotatingFileHandler(
        file_path, maxBytes=50 * 1024 * 1024, backupCount=10,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    root.info("Logging initialized", extra={"phase": "startup"})


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the fincoach namespace."""
    return logging.getLogger(f"fincoach.{name}")
