"""
Dependency management utilities for the replay system.

This module provides utilities for discovering and managing dependencies
required by the replay system. Dependencies are stored in a standardized
directory structure and can include:

- External tools and binaries
- Configuration files
- Data files
- Other project dependencies

The module provides functions to:
- List all available dependencies
- Get absolute paths to dependency directories
- Access the root dependency directory location

Dependencies are expected to be organized as subdirectories within
the main dependencies folder, with each subdirectory representing
a separate dependency or tool.
"""

import os
from typing import List

# Define the root directory for dependencies
# This path is relative to the current file location: ../dependencies
DEPENDENCY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dependencies"))


def dependency_list(
    full_path: bool = False,
) -> List[str]:
    """
    Get a list of all dependencies in the dependency root directory.

    This function scans the dependency root directory and returns a list
    of all items (directories and files) found within it. It's primarily
    used to discover available dependencies for the replay system.

    Args:
        full_path: If True, returns absolute paths to each dependency item.
                  If False, returns only the names of the dependency items.
                  Default is False.

    Returns:
        List[str]: A list containing either dependency names (if full_path=False)
                  or absolute paths to dependencies (if full_path=True).
                  The list may be empty if the dependency directory doesn't exist
                  or contains no items.
                  
    Raises:
        OSError: If the dependency root directory cannot be accessed
    """
    if full_path:
        # Return list of absolute paths to each dependency item
        return [os.path.join(DEPENDENCY_ROOT, i) for i in os.listdir(DEPENDENCY_ROOT)]
    else:
        # Return list of dependency names only
        return [i for i in os.listdir(DEPENDENCY_ROOT)]


def dependency_root() -> str:
    """
    Get the absolute path to the dependency root directory.

    This function returns the absolute path to the main directory where
    all dependencies are stored. This is useful for constructing paths
    to specific dependency subdirectories or for directory existence checks.

    Returns:
        str: The absolute path to the dependency root directory.
             This path is computed relative to the current module location
             and points to the '../dependencies' directory.

    Note:
        The returned path may not exist if the dependencies directory
        hasn't been created yet. Callers should check for existence
        if needed using os.path.exists() or similar functions.
    """
    return DEPENDENCY_ROOT
