"""
Operating system extension utilities for common OS operations.

This module provides utility functions that extend basic operating system
functionality with commonly needed operations such as:

- Finding available network ports for service binding
- Directory management with cleanup and recreation
- Safe file system operations

These utilities are designed to be simple, reliable, and handle common
edge cases that arise in system administration and development workflows.

Functions:
    os_free_port: Find an available port number for network services
    os_remkdirs: Remove and recreate directory (fresh directory creation)

Dependencies:
    - os: For file system operations
    - shutil: For advanced file operations like directory tree removal
    - socket: For network port operations
"""

import os
import shutil
import socket


def os_free_port() -> int:
    """
    Get a random free port number currently not in use on the system.

    This function uses the OS's automatic port assignment feature to find
    an available port. It creates a temporary socket, binds it to port 0
    (which tells the OS to assign any available port), retrieves the assigned
    port number, and then closes the socket.

    Returns:
        An available port number that was free at the time of the call

    Raises:
        OSError: If no ports are available (highly unlikely) or if there are
                socket operation failures

    Note:
        There's a small race condition where the port might be taken by another
        process between when this function returns and when you actually bind to it.
        This is generally not an issue for development and testing scenarios.

        The SO_REUSEADDR socket option is set to allow quick reuse of the port
        after the socket is closed, which helps prevent "Address already in use" errors.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Bind to port 0 to let the OS assign any available port
        s.bind(("", 0))
        # Set SO_REUSEADDR to allow rapid reuse of the port after socket closure
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Get the actual port number assigned by the OS
        return s.getsockname()[1]


def os_remkdirs(
    path: str,
) -> None:
    """
    Remove a directory if it exists and then create it (ensure fresh empty directory).

    This function provides a "fresh directory" operation by first removing the
    directory and all its contents if it exists, then creating a new empty
    directory at the same path. This is useful for cleaning up test directories,
    temporary workspaces, or ensuring a clean state for operations that require
    an empty directory.

    Args:
        path: The filesystem path to the directory to remove and recreate.
              Can be absolute or relative to the current working directory.

    Returns:
        None

    Raises:
        PermissionError: If insufficient permissions to remove or create the directory
        OSError: For other filesystem-related errors (disk full, invalid path, etc.)

    Safety Notes:
        - This function will permanently delete all contents of the directory
        - Use with caution as deleted data cannot be recovered
        - Consider backing up important data before using this function
        - The function is safe to call even if the directory doesn't exist

    Implementation Details:
        Uses shutil.rmtree() for recursive removal which handles nested directories,
        files, and symbolic links safely. The os.makedirs() call creates the
        directory and any necessary parent directories.
    """
    # Remove the entire directory tree if it exists (recursive deletion)
    if os.path.exists(path):
        shutil.rmtree(path)
    # Create a fresh empty directory (including any necessary parent directories)
    os.makedirs(path)
