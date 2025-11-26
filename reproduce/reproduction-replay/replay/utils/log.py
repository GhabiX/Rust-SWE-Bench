"""
Logging utilities for flexible and context-managed logging in SWE agent workflows.

This module provides context manager wrappers and convenience functions for creating
console, file, and null loggers with consistent formatting and resource management.
It also provides simple helpers for info and error logging with optional logger support.

Features:
    - Context-managed logger lifecycle (auto-close handlers)
    - Console, file, and null logger creation with custom formatting
    - Info and error logging helpers that are safe to call with None

Classes:
    LoggerContext: Context manager for logger resource cleanup

Functions:
    log_open_console_logger: Create a context-managed console logger
    log_open_file_logger: Create a context-managed file logger
    log_open_null_logger: Create a context-managed null logger
    log_info: Log info messages if logger is provided
    log_error: Log error messages if logger is provided
"""

import logging
import uuid
from typing import Optional


class LoggerContext:
    """
    Context manager for automatic logger resource cleanup.

    Ensures that all handlers attached to the logger are closed and removed
    when exiting the context, preventing resource leaks (especially for file handlers).

    Example:
        >>> with log_open_console_logger() as logger:
        ...     logger.info("Hello, world!")
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def __enter__(self) -> logging.Logger:
        # Return the logger instance for use within the context
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close and remove all handlers to avoid resource leaks
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)


def log_open_console_logger(
    name: Optional[str] = None,
    level: int = logging.INFO,
    formatter: Optional[logging.Formatter] = None,
) -> LoggerContext:
    """
    Create a context-managed logger that outputs to the console (stdout).

    Args:
        name: Logger name. If None, a unique name is generated.
        level: Logging level (e.g., logging.INFO, logging.DEBUG).
        formatter: Optional log message formatter. If None, a default formatter is used.

    Returns:
        LoggerContext: Context manager for the logger.

    Example:
        >>> with log_open_console_logger(level=logging.DEBUG) as logger:
        ...     logger.info("Console log message")
    """
    name = name or f"console_{uuid.uuid4()}"  # Generate unique logger name if not provided
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = formatter or logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False  # Prevent duplicate logs if parent handlers exist
    return LoggerContext(logger)


def log_open_file_logger(
    path: str,
    name: Optional[str] = None,
    level: int = logging.INFO,
    formatter: Optional[logging.Formatter] = None,
) -> LoggerContext:
    """
    Create a context-managed logger that outputs to a file.

    Args:
        path: Filesystem path to the log file. The file will be created if it does not exist.
        name: Logger name. If None, a unique name is generated.
        level: Logging level (e.g., logging.INFO, logging.DEBUG).
        formatter: Optional log message formatter. If None, a default formatter is used.

    Returns:
        LoggerContext: Context manager for the logger.

    Example:
        >>> with log_open_file_logger("output.log") as logger:
        ...     logger.error("This goes to the file!")
    """
    name = name or f"file_{uuid.uuid4()}"  # Generate unique logger name if not provided
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = formatter or logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler = logging.FileHandler(path)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False  # Prevent duplicate logs if parent handlers exist
    return LoggerContext(logger)


def log_open_null_logger(
    name: Optional[str] = None,
    level: int = logging.INFO,
) -> LoggerContext:
    """
    Create a context-managed logger that discards all log messages (null logger).

    Useful for disabling logging in test or production environments where log output
    is not needed. The logger is still context-managed for API consistency.

    Args:
        name: Logger name. If None, a unique name is generated.
        level: Logging level (has no effect for null logger).

    Returns:
        LoggerContext: Context manager for the logger.

    Example:
        >>> with log_open_null_logger() as logger:
        ...     logger.info("This will not be shown anywhere.")
    """
    name = name or f"null_{uuid.uuid4()}"  # Generate unique logger name if not provided
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # Prevent propagation to parent loggers
    return LoggerContext(logger)


def log_info(
    logger: Optional[logging.Logger],
    content: str,
) -> None:
    """
    Log an info-level message if a logger is provided.

    This helper is safe to call with logger=None (no-op in that case).

    Args:
        logger: Logger instance, or None to disable logging.
        content: Message to log at INFO level.
    """
    if logger:
        logger.info(content)


def log_error(
    logger: Optional[logging.Logger],
    content: str,
) -> None:
    """
    Log an error-level message if a logger is provided.

    This helper is safe to call with logger=None (no-op in that case).

    Args:
        logger: Logger instance, or None to disable logging.
        content: Message to log at ERROR level.
    """
    if logger:
        logger.error(content)
