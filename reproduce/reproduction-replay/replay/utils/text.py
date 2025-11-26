"""
Text Processing Utilities for Replay System

This module provides specialized text processing functions for handling various
types of textual output from development tools and command-line utilities.
It includes functions for cleaning up cargo warnings, grep output formatting,
and general text manipulation tasks commonly needed in replay systems.

Key Features:
- Cargo warning removal from build output
- Grep line number stripping for cleaner output
- Line break normalization and removal
- Regex-based text filtering and cleanup

Use Cases:
- Processing build tool output for clean logs
- Normalizing command output for comparison
- Preparing text data for analysis and storage
- Cleaning up multi-line output for single-line formats

Dependencies:
- re: Python regular expression library for pattern matching
"""

import re


def text_remove_cargo_warning(
    text: str,
) -> str:
    """
    Remove cargo warning blocks and individual warning lines from build output.

    This function cleans up Rust cargo build output by removing both multi-line
    warning blocks (including file references and code snippets) and standalone
    warning lines. It's particularly useful for focusing on errors and successful
    build information while filtering out non-critical warnings.

    Args:
        text: Input text containing cargo build output with potential warnings.
              Can include multi-line output with various cargo messages.

    Returns:
        Cleaned text with all cargo warning content removed and whitespace trimmed.
        Empty lines created by warning removal are also cleaned up.

    Warning Block Pattern:
        Matches cargo warnings that follow the structure:
        - "warning: <message>" line
        - " --> <file>:<line>:<col>" file reference
        - Optional code context lines
        - Blank line separator

    Use Cases:
        - Processing cargo build logs for error analysis
        - Creating clean build summaries without warnings
        - Filtering output for automated testing systems
        - Preparing cargo output for user display
    """
    # Regex pattern to match complete cargo warning blocks with file references and context
    cargo_warning_block_regex = r"(warning: .*\n)( *--> *.*\n)(.+\n)*\n"

    # Regex pattern to match standalone warning lines without file context
    cargo_warning_line_regex = r"warning: .*\n"

    # Remove multi-line warning blocks first (more specific pattern)
    text = re.sub(cargo_warning_block_regex, "", text)

    # Remove any remaining standalone warning lines
    text = re.sub(cargo_warning_line_regex, "", text)

    # Return cleaned text with leading/trailing whitespace removed
    return text.strip()


def text_remove_grep_line_number(
    text: str,
) -> str:
    """
    Remove line numbers from grep output to extract clean content lines.

    This function processes grep command output that includes line numbers,
    removing the numeric prefixes to return just the matched text content.
    It handles both colon-separated (grep -n) and dash-separated (grep -A/-B)
    line number formats commonly used in grep output.

    Args:
        text: Input text containing grep output with line numbers.
              Each line should start with a number followed by ':' or '-'.

    Returns:
        Cleaned text with line numbers removed from each line and
        leading/trailing whitespace trimmed from the entire result.

    Line Number Patterns:
        - "number:" - Standard grep match with line number
        - "number-" - Grep context lines (before/after matches)
        - Removes digits from start of line until first ':' or '-'

    Processing Steps:
        1. Split input into individual lines
        2. Strip whitespace from each line
        3. Remove line number prefix (digits + ':' or '-') from each line
        4. Join cleaned lines back together
        5. Trim final whitespace

    Use Cases:
        - Processing grep search results for clean display
        - Extracting matched content without line references
        - Preparing grep output for further text analysis
        - Creating clean code excerpts from search results
    """
    # Process each line: split by newlines, strip whitespace, remove line number prefix
    cleaned_lines = []
    for line in text.splitlines():
        # Strip whitespace and remove line number prefix (digits followed by : or -)
        cleaned_line = re.sub(r"^\d+(:|-)", "", line.strip())
        cleaned_lines.append(cleaned_line)

    # Join all cleaned lines back together and trim final whitespace
    return "\n".join(cleaned_lines).strip()


def text_remove_line_break(
    text: str,
) -> str:
    """
    Remove all line breaks from text to create a single-line string.

    This function converts multi-line text into a single continuous line by
    replacing all newline characters with empty strings. It's useful for
    normalizing text data, creating compact representations, or preparing
    text for systems that expect single-line input.

    Args:
        text: Input text that may contain newline characters (\n).
              Can be empty, single-line, or multi-line text.

    Returns:
        Text with all newline characters removed, creating one continuous line.
        Other whitespace characters (spaces, tabs) are preserved.

    Use Cases:
        - Converting error messages to single-line format for logging
        - Preparing multi-line command output for compact storage
        - Creating single-line representations for JSON or CSV fields
        - Normalizing text data for comparison or hashing
        - Processing text for systems that don't handle newlines well

    Note:
        This function only removes newline characters (\n). Other whitespace
        like spaces and tabs are preserved. If you need to normalize all
        whitespace, consider using additional string methods after this function.

    Performance:
        This is an efficient operation using Python's built-in string.replace()
        method, which performs the replacement in a single pass through the text.
    """
    # Replace all newline characters with empty strings to create single line
    return text.replace("\n", "")
