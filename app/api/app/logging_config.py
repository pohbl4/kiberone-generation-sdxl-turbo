from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path

from .config import get_settings

_CONFIGURED = False


def _build_log_file_path(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "api.log"


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    log_file = _build_log_file_path(settings.log_dir)
    log_file_path = str(log_file)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "access": {
                    "format": "%(asctime)s | %(levelname)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "default",
                },
                "file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "level": "INFO",
                    "formatter": "default",
                    "filename": log_file_path,
                    "when": "midnight",
                    "interval": 1,
                    "backupCount": 2,
                    "encoding": "utf-8",
                    "delay": True,
                },
                "access_file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "level": "INFO",
                    "formatter": "access",
                    "filename": log_file_path,
                    "when": "midnight",
                    "interval": 1,
                    "backupCount": 2,
                    "encoding": "utf-8",
                    "delay": True,
                },
            },
            "loggers": {
                "": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                },
                "uvicorn": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console", "file"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console", "access_file"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )

    logging.getLogger(__name__).info("Logging configured. Writing to %s", log_file_path)
    _CONFIGURED = True
