"""Centralized logging configuration."""

import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging(level: Optional[str] = None) -> None:
    """Configure application-wide logging."""
    settings = get_settings()
    log_level = level or settings.LOG_LEVEL

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("uvicorn.access", "elasticsearch", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance."""
    return logging.getLogger(name)
