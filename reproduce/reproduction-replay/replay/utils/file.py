"""
File I/O utilities for text and JSON Lines (JSONL) file operations.

This module provides simple, consistent interfaces for common file operations
including text file reading/writing and JSON Lines format handling. All functions
use UTF-8 encoding by default and handle file operations with proper context
management for automatic resource cleanup.

JSON Lines format (JSONL) is used for storing structured data where each line
contains a valid JSON object, making it suitable for streaming processing of
large datasets or append-only logging of structured events.

Functions:
    file_read_text: Read complete contents of a text file
    file_write_text: Write text to a file, replacing existing contents
    file_append_json_line: Append a dictionary as a JSON line to a file
    file_load_jsonl: Load a JSONL file into a list of dictionaries

Dependencies:
    - json: For JSON serialization/deserialization
    - os: For file system operations (imported but may be used by callers)
"""

import json
from typing import Dict, List


def file_read_text(path: str) -> str:
    """
    Read the entire contents of a text file using UTF-8 encoding.

    This function reads the complete contents of a text file into memory.
    It's suitable for small to medium-sized files where you need the entire
    content at once. For large files, consider streaming approaches.

    Args:
        path: The filesystem path to the file to read. Can be absolute
              or relative to the current working directory.

    Returns:
        The complete contents of the file as a UTF-8 decoded string.
        Empty string if the file is empty.

    Raises:
        FileNotFoundError: If the specified file does not exist
        PermissionError: If insufficient permissions to read the file
        UnicodeDecodeError: If the file cannot be decoded as UTF-8
        IOError: For other I/O related errors (disk full, network issues, etc.)

    Note:
        The file is automatically closed after reading, even if an exception occurs.
    """
    with open(path, "r", encoding="utf-8") as f:  # Explicitly specify UTF-8 encoding
        return f.read()  # Read entire file contents into memory


def file_write_text(path: str, text: str) -> None:
    """
    Write text to a file using UTF-8 encoding, replacing existing contents.

    This function writes the provided text to a file, creating the file if it
    doesn't exist or completely replacing the contents if it does exist.
    The parent directory must already exist.

    Args:
        path: The filesystem path where the file should be written. Can be
              absolute or relative to the current working directory.
        text: The text content to write to the file. Will be encoded as UTF-8.

    Returns:
        None

    Raises:
        FileNotFoundError: If the parent directory does not exist
        PermissionError: If insufficient permissions to write to the location
        IOError: For other I/O related errors (disk full, read-only filesystem, etc.)

    Warning:
        This function will completely overwrite existing files without warning.
        Use file_append_json_line() or similar functions if you need to append data.

    Note:
        The file is automatically closed and flushed after writing, even if
        an exception occurs during the write operation.
    """
    with open(path, "w", encoding="utf-8") as f:  # Explicitly specify UTF-8 encoding
        f.write(text)  # Write text content, replacing any existing content


def file_append_json_line(
    path: str,
    data: Dict,
) -> None:
    """
    Append a dictionary as a JSON line to a file in JSONL format.

    This function serializes a dictionary to JSON and appends it as a new line
    to the specified file. This creates or maintains a JSON Lines (JSONL) format
    file where each line contains a valid JSON object. This format is commonly
    used for streaming data processing and append-only logging.

    The function creates the file if it doesn't exist, or appends to existing
    content if it does exist. Each JSON object is written on a separate line.

    Args:
        path: The filesystem path to the JSONL file. Can be absolute or
              relative to the current working directory.
        data: Dictionary to serialize as JSON and append to the file.
              Must be JSON-serializable (no custom objects, functions, etc.).

    Returns:
        None

    Raises:
        TypeError: If the data dictionary contains non-JSON-serializable objects
        PermissionError: If insufficient permissions to write to the file
        IOError: For other I/O related errors (disk full, etc.)

    Note:
        - Each JSON object is written as a compact string without indentation
        - The file is automatically flushed and closed after each append
        - This function is thread-safe for individual writes but not for
          coordinated multi-line operations
    """
    with open(path, "a", encoding="utf-8") as f:  # Append mode with UTF-8 encoding
        # Serialize dictionary to compact JSON string
        json_string = json.dumps(data)
        # Write JSON string followed by newline to create JSONL format
        f.write(json_string + "\n")


def file_load_jsonl(
    path: str,
) -> List[Dict]:
    """
    Load a JSON Lines (JSONL) file into a list of dictionaries.

    This function reads a JSONL file where each line contains a valid JSON object
    and returns a list containing all the parsed dictionaries. JSONL format is
    commonly used for structured data storage and streaming processing.

    The function loads the entire file into memory, so it's suitable for small
    to medium-sized JSONL files. For large files, consider streaming approaches
    that process one line at a time.

    Args:
        path: The filesystem path to the JSONL file to load. Can be absolute
              or relative to the current working directory.

    Returns:
        A list of dictionaries, where each dictionary represents one JSON object
        from a line in the file. Returns an empty list if the file is empty.

    Raises:
        FileNotFoundError: If the specified file does not exist
        json.JSONDecodeError: If any line contains invalid JSON
        UnicodeDecodeError: If the file cannot be decoded as UTF-8
        PermissionError: If insufficient permissions to read the file
        IOError: For other I/O related errors

    Note:
        - Each line must contain exactly one valid JSON object
        - Empty lines will cause JSONDecodeError
        - The file is automatically closed after reading
        - All data is loaded into memory at once

    Performance:
        For files with thousands of entries, consider the memory usage.
        Each dictionary consumes memory proportional to its data size.
    """
    with open(path, "r", encoding="utf-8") as f:  # Read with UTF-8 encoding
        # Parse each line as JSON and collect into a list
        return [json.loads(line.strip()) for line in f if line.strip()]  # Parse JSON, strip whitespace for robustness  # Iterate through each line in the file  # Skip empty lines to avoid JSONDecodeError
