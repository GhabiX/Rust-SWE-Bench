"""
UUID Generation Utilities for Replay System

This module provides simple utilities for generating unique identifiers using
Python's built-in UUID (Universally Unique Identifier) library. It offers
convenient functions for creating random UUIDs in string format, which are
commonly needed for tracking instances, sessions, and temporary resources.

Key Features:
- Random UUID generation using UUID4 algorithm
- String format output for easy integration
- Thread-safe unique identifier generation
- Cross-platform compatibility

Use Cases:
- Generating unique identifiers for replay sessions
- Creating temporary file or directory names
- Tracking individual instances or requests
- Generating unique keys for data structures
- Creating correlation IDs for logging and debugging

Technical Details:
- Uses UUID4 (random UUID) algorithm for maximum uniqueness
- Generated UUIDs have extremely low probability of collision
- Standard format: 8-4-4-4-12 hexadecimal digits (36 characters total)
- Example: "550e8400-e29b-41d4-a716-446655440000"

Dependencies:
- uuid: Python standard library for UUID generation
"""

import uuid


def uuid_str() -> str:
    """
    Generate a random UUID and return it as a string.

    This function creates a new universally unique identifier using the UUID4
    algorithm (random UUID generation) and converts it to a standard string
    representation. Each call produces a new, statistically unique identifier
    suitable for use as keys, session IDs, or temporary resource names.

    Returns:
        A string representation of a random UUID in the standard format:
        "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx" where x is any hexadecimal
        digit and y is one of 8, 9, A, or B (36 characters total including hyphens).

    UUID4 Properties:
        - Version 4 UUID (random or pseudo-random generation)
        - 122 bits of randomness
        - Collision probability: ~5.3 x 10^-37 for 1 billion UUIDs
        - No dependency on MAC address or timestamp
        - Cryptographically secure random number generation

    Performance:
        - Very fast generation (~microseconds per call)
        - No network or file I/O required
        - Thread-safe and can be called concurrently
        - Minimal memory footprint

    Use Cases:
        - Unique identifiers for replay sessions or instances
        - Temporary file and directory naming
        - Database primary keys or correlation IDs
        - Session tracking in web applications
        - Message or event correlation in distributed systems
        - Cache keys for temporary data storage

    Thread Safety:
        This function is thread-safe and can be called from multiple threads
        concurrently without synchronization concerns. Each call will produce
        a unique identifier regardless of timing or threading context.

    Format Specification:
        The returned string follows RFC 4122 standard format:
        - 32 hexadecimal digits displayed in 5 groups
        - Separated by hyphens: 8-4-4-4-12
        - Total length: 36 characters including 4 hyphens
        - Case: lowercase hexadecimal letters (a-f)
    """
    # Generate a random UUID using UUID4 algorithm and convert to string format
    return str(uuid.uuid4())
