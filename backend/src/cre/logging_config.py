"""structlog setup: human-readable locally, JSON in deployed environments."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(env: str = "local", debug: bool = True) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    # ffmpeg/mediapipe are chatty on import
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if env == "local":
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    else:
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
