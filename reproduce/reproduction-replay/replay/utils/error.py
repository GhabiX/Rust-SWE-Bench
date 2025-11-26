"""
Error handling utilities for consistent exception formatting and logging.

This module provides standardized functions for converting Python exceptions
into formatted strings suitable for different use cases:

- Single-line format for compact logging and terminal output
- Multi-line format for detailed error reports and debugging

The functions handle traceback information consistently and provide clean
formatting for both automated logging systems and human-readable output.

Functions:
    error_single_line_message: Convert exception to compact single-line format
    error_message: Convert exception to detailed multi-line format with markdown
"""
import traceback

from replay.utils.text import text_remove_line_break


def error_single_line_message(
    error: Exception,
) -> str:
    """
    Convert an exception with traceback into a single line message.

    This function combines the exception traceback with the error message
    and removes line breaks to create a single line output, which is useful
    for logging or displaying errors in compact format where space is limited.

    The function captures the full traceback context at the time it's called,
    ensuring that stack trace information is preserved even if the exception
    is re-raised or modified later.

    Args:
        error: The exception to convert. Can be any Exception subclass.

    Returns:
        A single-line string containing the complete traceback and error message,
        with all newlines and whitespace normalized for compact display.

    Note:
        This function calls traceback.format_exc() which captures the current
        exception context, so it should be called from within an exception handler.
    """
    # Combine full traceback and error message, then normalize to single line
    full_traceback = traceback.format_exc()  # Get complete stack trace
    error_string = str(error)  # Convert exception to string representation
    combined_message = full_traceback + error_string
    
    # Remove line breaks and normalize whitespace for compact display
    return text_remove_line_break(combined_message)


def error_message(
    error: Exception,
) -> str:
    """
    Convert an exception into a formatted multi-line error message with markdown.

    This function creates a detailed, human-readable error report that includes
    both the exception details and full traceback information, formatted with
    markdown code blocks for better readability in documentation, logs, or
    issue reports.

    Unlike error_single_line_message(), this function preserves the multi-line
    format of tracebacks and presents them in a structured way suitable for
    detailed error analysis and debugging.

    Args:
        error: The exception to convert. Can be any Exception subclass.

    Returns:
        A multi-line string containing the exception and traceback information
        wrapped in markdown code blocks for enhanced readability.
        
    Note:
        The output includes markdown formatting which makes it suitable for
        documentation systems, issue trackers, or any context where formatted
        text display is supported.
    """
    # Get the current exception traceback context
    full_traceback = traceback.format_exc()
    
    # Format as markdown code block with clear labels
    formatted_message = f"```\nException: {error}\nTraceback: {full_traceback}\n```"
    
    # Strip any trailing whitespace for clean output
    return formatted_message.strip()
