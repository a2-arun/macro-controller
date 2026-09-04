"""Structured logging. The original had none -- failures surfaced as message
boxes or as nothing at all, which makes a background hotkey app very hard to
debug."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.paths import log_dir

_configured = False


def configure(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s"
    )

    handler = RotatingFileHandler(
        log_dir() / "custommacro.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    _configured = True
