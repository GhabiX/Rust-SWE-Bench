"""
Cargo output parsing utilities for Rust error and warning extraction.

This module provides tools for parsing Cargo (Rust's build tool) output to extract
error codes, warning messages, and compiler diagnostics. It includes:

- CargoErrorDoc: Fetches official Rust error documentation from rust-lang.org
- Line-based extractors: Extract simple warning/error messages from single lines
- Block-based extractors: Extract detailed diagnostics with file locations

The extractors support both simple format (just messages) and detailed format
(with error codes, file paths, line numbers, and column positions).
"""

from functools import lru_cache
import re
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from lxml import etree

import requests


class CargoErrorDoc:
    """
    Utility class for retrieving official Rust error code documentation.

    This class provides access to the official Rust error documentation
    hosted at doc.rust-lang.org. It fetches HTML pages for specific error
    codes and extracts the textual content for analysis or display.

    The class uses LRU caching to avoid repeated network requests for the
    same error codes, improving performance when processing multiple
    instances of the same errors.
    """

    def __init__(self):
        """
        Initialize the CargoErrorDoc instance.

        Currently no initialization is required, but the constructor
        is provided for future extensibility.
        """
        pass

    @lru_cache(maxsize=1000)
    def get_error_code_detail(
        self,
        error_code: str,
    ) -> str:
        """
        Retrieve detailed documentation for a specific Rust error code.

        This method fetches the official documentation page for a given Rust
        error code from doc.rust-lang.org and extracts the textual content.
        Results are cached to avoid repeated network requests.

        Args:
            error_code: The Rust error code to look up (e.g., 'E0308', 'e0277')
                       Case-insensitive; will be converted to uppercase

        Returns:
            str: The extracted documentation text content for the error code

        Raises:
            requests.HTTPError: If the HTTP request fails (e.g., 404 for invalid codes)
            requests.RequestException: For other network-related errors

        Examples:
            >>> doc = CargoErrorDoc()
            >>> content = doc.get_error_code_detail("E0308")
            >>> print("Type mismatch" in content)  # Likely True for E0308
        """
        # Fetch the HTML documentation page
        response = requests.get(url=f"https://doc.rust-lang.org/error_codes/{error_code.upper()}.html")
        response.raise_for_status()  # Raise exception for HTTP errors

        # Parse HTML and extract text content from the main documentation area
        html = etree.HTML(response.text)
        # XPath selects all text nodes within the main content div, filtering out empty/whitespace-only text
        return "\n".join(html.xpath(f"//div[@id='content']/main//text()[normalize-space()]"))


def cargo_extract_line_warning(
    text: str,
) -> List[str]:
    """
    Extract warning messages from Cargo output using line-based pattern matching.

    This function searches for lines that start with "warning: " and extracts
    the warning message portion. It's useful for getting a quick overview of
    all warnings without detailed location information.

    Args:
        text: The complete Cargo build output as a string

    Returns:
        List[str]: List of warning message strings (without the "warning: " prefix)
    """
    # Use MULTILINE flag to match ^ at the beginning of each line
    return re.findall(r"^warning: (.*)$", text, re.MULTILINE)


def cargo_extract_line_error(
    text: str,
) -> List[Tuple[Optional[str], str]]:
    """
    Extract error messages and codes from Cargo output using line-based pattern matching.

    This function searches for lines that start with "error" (optionally followed by
    an error code in brackets) and extracts both the error code and message.

    Args:
        text: The complete Cargo build output as a string

    Returns:
        List[Tuple[Optional[str], str]]: List of (error_code, message) tuples.
                                        error_code is None if no code was specified.
    """
    # Regex matches:
    # - "error" at line start
    # - Optional error code in square brackets like [E0308]
    # - Colon and space
    # - The error message (captured)
    errors = re.findall(r"^error(?:\[(E\d{4})\])?: (.*)$", text, re.MULTILINE)
    # Convert empty string error codes to None for consistency
    errors = [(a if a else None, b) for a, b in errors]
    return errors


def cargo_extract_block_warning(
    text: str,
) -> List[Tuple[str, str, int, int]]:
    """
    Extract detailed warning messages with source location from Cargo output.

    This function searches for warning blocks that include the warning message
    followed by source location information (file path, line, and column).
    It's more detailed than line-based extraction and provides exact locations.

    Args:
        text: The complete Cargo build output as a string

    Returns:
        List[Tuple[str, str, int, int]]: List of (message, file_path, line, column) tuples
                                        where line and column are 1-based integers
    """
    # Regex matches warning blocks with location info:
    # - "warning: " followed by message
    # - Newline and "   --> " (exact spacing important)
    # - File path, colon, line number, colon, column number
    warnings = re.findall(
        r"warning: (.*)\n   --> (.*):(\d+):(\d+)\n",
        text,
    )
    # Convert string line/column numbers to integers
    warnings = [(a, b, int(c), int(d)) for a, b, c, d in warnings]
    return warnings


def cargo_extract_block_error(text: str) -> List[Tuple[Optional[str], str, str, int, int]]:
    """
    Extract detailed error messages with source location from Cargo output.

    This function searches for error blocks that include the error message,
    optional error code, and source location information (file path, line, and column).
    It provides the most comprehensive error information available from Cargo output.

    Args:
        text: The complete Cargo build output as a string

    Returns:
        List[Tuple[Optional[str], str, str, int, int]]: List of tuples containing:
            - error_code: Rust error code (e.g., 'E0308') or None if not specified
            - message: The error message text
            - file_path: Path to the source file where the error occurred
            - line: Line number (1-based) where the error occurred
            - column: Column position (1-based) where the error occurred
    """
    # Regex matches error blocks with location info:
    # - "error" optionally followed by error code in square brackets
    # - Colon, space, and error message
    # - Newline and "   --> " (exact spacing important)
    # - File path, colon, line number, colon, column number
    errors = re.findall(
        r"error(?:\[(E\d{4})\])?: (.*)\n   --> (.*):(\d+):(\d+)\n",
        text,
    )
    # Convert empty string error codes to None and string numbers to integers
    errors = [(a if a else None, b, c, int(d), int(e)) for a, b, c, d, e in errors]
    return errors
