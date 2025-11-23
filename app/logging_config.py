"""Central logging configuration for the Crypto Analyst chatbot."""

from __future__ import annotations

import logging
import os
from logging.config import dictConfig


def setup_logging() -> None:
    """Configure application-wide logging."""

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if getattr(setup_logging, "_configured", False):
        return

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                },
            },
            "handlers": {
                "default": {
                    "level": level,
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                }
            },
            "loggers": {
                "": {"handlers": ["default"], "level": level, "propagate": False},
            },
        }
    )
    logging.getLogger(__name__).debug("Logging configured at level %s", level)
    setup_logging._configured = True
