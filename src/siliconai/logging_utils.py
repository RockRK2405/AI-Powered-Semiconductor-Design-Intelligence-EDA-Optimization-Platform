"""Logging setup shared by scripts and services."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging once. Safe to call repeatedly."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_FORMAT)
    root.setLevel(level)
