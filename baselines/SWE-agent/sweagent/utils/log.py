from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

_SET_UP_LOGGERS = set()


def get_logger(name: str, log_dir: Path = None) -> logging.Logger:
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        name = f"{log_dir.name}_{name}"
    logger = logging.getLogger(name)
    if name in _SET_UP_LOGGERS:
        # Already set up
        return logger
    handler = RichHandler(show_time=False, show_path=False)
    handler.setLevel(logging.DEBUG)
    if log_dir is not None:
        file_handler = logging.FileHandler(log_dir / "log")
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        handler.setLevel(logging.ERROR)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    _SET_UP_LOGGERS.add(name)
    return logger


default_logger = get_logger("swe-agent")
