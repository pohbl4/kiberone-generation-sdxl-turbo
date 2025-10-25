from __future__ import annotations

import logging
import os
from logging.config import dictConfig
from pathlib import Path

_CONFIGURED = False


def _resolve_log_dir() -> Path:
    raw_dir = os.getenv("INFERENCE_LOG_DIR") or os.getenv("LOG_DIR") or "logs"
    path = Path(raw_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = _resolve_log_dir()
    log_file = log_dir / "inference.log"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "standard",
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "level": "INFO",
                    "formatter": "standard",
                    "filename": str(log_file),
                    "when": "midnight",
                    "interval": 1,
                    "backupCount": 2,
                    "encoding": "utf-8",
                    "delay": True,
                },
            },
            "loggers": {
                "": {"handlers": ["console", "file"], "level": "INFO"},
            },
        }
    )

    logging.getLogger(__name__).info("Inference logging configured. Writing to %s", log_file)
    _CONFIGURED = True
