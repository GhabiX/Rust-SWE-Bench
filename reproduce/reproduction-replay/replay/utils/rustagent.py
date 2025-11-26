"""
RustAgent utilities for log file processing and function call parsing.

This module provides utilities specifically designed for working with RustAgent
(RTA) log files and trajectory data. It handles:

- Log file path parsing and instance name extraction
- Function call extraction from agent responses
- Complex function call string parsing with multi-line content
- Support for different RustAgent function types (execute_bash, str_replace, new_file, test_report)

The module supports both current and deprecated log file naming conventions,
ensuring compatibility with different versions of RustAgent outputs.

Key Features:
    - Instance name extraction from log file paths
    - Bi-directional mapping between instance names and log file paths
    - Code block extraction with language identifier cleaning
    - Advanced function call parsing with multi-line parameter support
    - Support for execute_bash, str_replace, new_file, and test_report functions

Functions:
    rustagent_extract_instance_name_from_log_path: Extract instance name from log path
    rustagent_instance_name_to_log_file_path: Find log file path for instance name
    rustagent_extract_function_calls: Extract function call blocks from text
    rustagent_function_call_loads: Parse function call strings into structured data

Log File Format:
    Current: rta_log_{owner}__{repo}-{pr}.json
    Deprecated: rta_log_{owner}__{repo}_{pr}.json
"""

import os
import re
from typing import Any
from typing import Dict
from typing import List


def rustagent_extract_instance_name_from_log_path(
    log_path: str,
) -> str:
    """
    Extract instance name from a RustAgent log file path.

    Parses the log file name to extract the GitHub repository information
    and reconstruct the standard instance name format. The function handles
    the current RustAgent log naming convention.

    Args:
        log_path: Full path to the RustAgent log file. The filename should follow
                 the format "rta_log_{owner}__{repo}-{pr}.json"

    Returns:
        Instance name in the format "{owner}__{repo}__{pr}"

    Raises:
        ValueError: If the log path doesn't match the expected RustAgent log file format

    Note:
        This function only handles the current log file format with dash separator
        for PR numbers. It expects the pattern "rta_log_{owner}__{repo}-{pr}.json".
    """
    log_name = os.path.basename(log_path)  # Extract filename from full path
    # Parse the log filename using regex to extract owner, repo, and PR components
    match = re.match(r"rta_log_(.*)__(.*)-(.*).json", log_name)
    if not match:
        raise ValueError(f"Invalid log path: {log_path}")
    # Reconstruct instance name in standard format
    return f"{match.group(1)}__{match.group(2)}__{match.group(3)}"


def rustagent_instance_name_to_log_file_path(
    log_dir_path: str,
    instance_name: str,
) -> str:
    """
    Find the RustAgent log file path for a given instance name.

    This function searches for RustAgent log files using both current and
    deprecated naming conventions. It first tries the current format with
    dash separator, then falls back to the deprecated underscore format
    for backward compatibility.

    Args:
        log_dir_path: Directory path where RustAgent log files are stored
        instance_name: Instance name in format "{owner}__{repo}__{pr}"

    Returns:
        Full path to the existing log file

    Raises:
        ValueError: If no log file is found for the given instance in either format

    Note:
        The function performs filesystem checks to ensure the file exists
        before returning the path. It prioritizes the current format over
        the deprecated format.
    """
    # Parse instance name into components
    owner, repo, pr = instance_name.split("__")

    # Try current format first (dash separator for PR)
    path = os.path.join(log_dir_path, f"rta_log_{owner}__{repo}-{pr}.json")
    if os.path.exists(path):
        return path

    # Fall back to deprecated format (underscore separator for PR)
    path = os.path.join(log_dir_path, f"rta_log_{owner}__{repo}_{pr}.json")
    if os.path.exists(path):
        return path

    # Neither format found - raise informative error
    raise ValueError(f"Log path not found in {log_dir_path}, finding rta_log_{owner}__{repo}-{pr}.json or rta_log_{owner}__{repo}_{pr}.json")


def rustagent_extract_function_calls(text: str) -> List[str]:
    """
    Extract function call code blocks from text, removing language identifiers.

    This function searches for markdown-style code blocks (```...```) in the input
    text, processes them to remove programming language identifiers, and filters
    to return only blocks that contain RustAgent function calls (starting with "function:").

    Args:
        text: Input text that may contain markdown code blocks with function calls

    Returns:
        List of cleaned function call code blocks (as strings) that start with 'function:'.
        Each block has language identifiers removed but preserves the actual function content.

    Processing Steps:
        1. Extract all markdown code blocks using regex pattern ```...```
        2. Remove language identifiers (python, bash, rust, etc.) from block headers
        3. Filter blocks to only include those starting with "function:"
        4. Return cleaned function call blocks

    Language Identifiers Removed:
        Supports common programming languages: python, bash, rust, js, javascript,
        typescript, go, java, c, cpp, csharp, ruby, php, swift, kotlin, scala,
        perl, r, shell, powershell, sql, html, css, xml, yaml, json, markdown, plaintext

    Note:
        Only blocks that start with "function:" after cleaning are returned.
        Empty or non-function blocks are filtered out.
    """
    # Extract all markdown code blocks using regex with DOTALL flag for multiline matching
    pattern = re.compile(r"```(.*?)```", re.DOTALL)
    blocks = [block.strip() for block in pattern.findall(text)]

    # Process each block to remove language identifiers
    cleaned_blocks = []
    for block in blocks:
        # Check if the block starts with a language identifier (e.g., python, bash, rust)
        lines = block.split("\n", 1)  # Split into first line and rest
        if len(lines) > 1 and re.match(r"^(python|bash|rust|js|javascript|typescript|ts|go|java|c|cpp|csharp|cs|ruby|php|swift|kotlin|scala|perl|r|shell|powershell|sql|html|css|xml|yaml|json|markdown|md|plaintext)$", lines[0].strip()):
            # Remove the language identifier line and keep only the code content
            cleaned_blocks.append(lines[1].strip())
        else:
            # No language identifier found, keep the entire block
            cleaned_blocks.append(block.strip())

    # Filter to only include blocks that contain RustAgent function calls
    function_blocks = [block for block in cleaned_blocks if block.strip().startswith("function:")]
    return function_blocks


def rustagent_function_call_loads(call_string: str) -> Dict[str, Any]:
    """
    Parse a RustAgent function call string into structured function name and parameters.

    This function handles the complex parsing of RustAgent's custom function call format,
    which supports multiple function types with different parameter structures. It can
    handle inline parameters, multi-line content, and various block markers depending
    on the function type.

    Supported Function Formats:

    1. execute_bash:
       ```
       function:execute_bash
       cmd:command here
       additional command lines...
       ```

    2. str_replace:
       ```
       function:str_replace
       file_path:/path/to/file
       old_str:text to replace
       new_str:replacement text
       ```

    3. new_file:
       ```
       function:new_file
       file_path:/path/to/new/file
       new_str:file content here
       ```

    4. test_report:
       ```
       function:test_report
       test_cmd:test command
       ```

    Args:
        call_string: The raw string representing the RustAgent function call.
                    Must start with 'function:<name>' and follow the specific
                    format for each function type.

    Returns:
        Dictionary containing:
        - "function_name" (str): The name of the function to execute
        - "parameters" (Dict[str, Any]): Dictionary of parsed parameters specific
          to the function type

    Raises:
        ValueError: If the call_string is malformed, doesn't start with 'function:',
                   contains unknown function types, or is missing required parameters

    Parameter Rules:
        - Parameters can be inline with function declaration or on separate lines
        - Multi-line content preserves whitespace and line breaks
        - Block markers (old_str:, new_str:) must appear in expected order
        - Empty parameter values are allowed for some functions

    Note:
        This parser is designed specifically for RustAgent's function call format
        and may not work with other agent systems. It handles edge cases like
        empty commands, inline vs. separate parameter lines, and multi-line content.
    """
    # Split input into lines while preserving original newlines for accurate parsing
    raw_lines_with_newlines = call_string.strip().splitlines(True)
    if not raw_lines_with_newlines:
        raise ValueError("API call string cannot be empty.")

    # Extract and parse the function declaration line
    first_line_full = raw_lines_with_newlines.pop(0)  # Consume the first line
    first_line_stripped = first_line_full.strip()

    # Match the function declaration pattern
    func_match = re.match(r"function:(\w+)", first_line_stripped)
    if not func_match:
        raise ValueError("API call must start with 'function:<name>'.")

    function_name = func_match.group(1)
    parameters = {}

    # Extract any inline content after the function declaration
    inline_content_after_func = first_line_stripped[func_match.end() :].strip()

    # Remaining lines after the function declaration (with original newlines preserved)
    # This list will be consumed (popped from) as parameters are parsed
    lines_after_func_decl = list(raw_lines_with_newlines)

    # Parse execute_bash function: handles command execution with multi-line support
    if function_name == "execute_bash":
        cmd_line_content = None  # Will store the stripped line containing "cmd:" prefix and its value

        # Check if cmd parameter is inline with function declaration
        if inline_content_after_func.startswith("cmd:"):
            cmd_line_content = inline_content_after_func
            # All remaining lines are part of the multi-line command
        elif lines_after_func_decl and lines_after_func_decl[0].strip().startswith("cmd:"):
            cmd_line_content = lines_after_func_decl.pop(0).strip()  # Consume cmd line
            # Remaining lines are additional command content
        else:
            raise ValueError("execute_bash: 'cmd:' parameter prefix is missing or malformed. It should be inline with 'function:execute_bash' or on the next line.")

        # Build the complete command from the cmd line and subsequent lines
        cmd_content_parts = []

        # Extract content from the "cmd:" line itself (after the prefix)
        content_on_cmd_line = cmd_line_content[len("cmd:") :].strip()
        if content_on_cmd_line:
            cmd_content_parts.append(content_on_cmd_line)

        # Append subsequent lines as additional command content
        # These lines preserve indentation but remove trailing newlines
        for line_with_nl in lines_after_func_decl:
            cmd_content_parts.append(line_with_nl.rstrip("\n"))  # Preserve leading spaces, remove trailing \n

        # Join all parts with newlines and strip outer whitespace
        parameters["cmd"] = "\n".join(cmd_content_parts).strip()
        # Note: An empty command string (e.g., "cmd:" followed by nothing) is allowed

    # Parse str_replace and new_file functions: handle file operations with content blocks
    elif function_name in ("new_file", "str_replace"):
        # 1. Parse file_path parameter (required first parameter for these functions)
        file_path_line_content = None  # Will store the stripped line content for file_path:

        if inline_content_after_func.startswith("file_path:"):
            # file_path is inline with function declaration
            file_path_line_content = inline_content_after_func
            # Remaining lines are for subsequent content blocks (old_str/new_str)
        elif inline_content_after_func:  # Inline content exists but it's not file_path
            raise ValueError(f"{function_name}: Unexpected inline content '{inline_content_after_func}'. Expected 'file_path:' or nothing.")
        elif lines_after_func_decl and lines_after_func_decl[0].strip().startswith("file_path:"):
            # file_path is on the next line after function declaration
            file_path_line_content = lines_after_func_decl.pop(0).strip()  # Consume file_path line
        else:
            raise ValueError(f"{function_name}: 'file_path:' parameter is missing. It should be inline with 'function:{function_name}' or on the next line.")

        # Extract and validate the file path value
        parameters["file_path"] = file_path_line_content[len("file_path:") :].strip()
        if not parameters["file_path"]:
            raise ValueError(f"{function_name}: 'file_path' value cannot be empty.")

        # 2. Parse content blocks (old_str, new_str) based on function type
        expected_block_markers_ordered = []
        if function_name == "str_replace":
            expected_block_markers_ordered = ["old_str:", "new_str:"]  # Both old and new content required
        elif function_name == "new_file":
            expected_block_markers_ordered = ["new_str:"]  # Only new content required for file creation

        # Stack of markers to find (will be popped as markers are discovered)
        markers_to_find_stack = list(expected_block_markers_ordered)

        # State variables for parsing content blocks
        current_block_key = None  # Current block being parsed (e.g., "old_str" without colon)
        current_block_content_lines = []  # Accumulated content lines for the current block

        # Process remaining lines to find and parse content blocks
        # lines_after_func_decl now contains lines after the file_path parameter
        idx = 0
        while idx < len(lines_after_func_decl):
            line_with_newline = lines_after_func_decl[idx]
            line_stripped = line_with_newline.strip()

            # Check if this line starts the next expected block marker
            next_expected_marker_prefix = markers_to_find_stack[0] if markers_to_find_stack else None

            if next_expected_marker_prefix and line_stripped.startswith(next_expected_marker_prefix):
                # Found the next expected marker - finalize previous block if any
                if current_block_key:
                    parameters[current_block_key] = "\n".join(current_block_content_lines).strip()

                # Start processing the new block
                markers_to_find_stack.pop(0)  # Remove this marker from the expected stack
                current_block_key = next_expected_marker_prefix[:-1]  # Store key without colon (e.g., "new_str")
                current_block_content_lines = []  # Reset content accumulator for new block

                # Check if content starts on the same line as the marker
                content_on_marker_line = line_stripped[len(next_expected_marker_prefix) :].strip()
                if content_on_marker_line:
                    current_block_content_lines.append(content_on_marker_line)
                idx += 1  # Move to the next line
            elif current_block_key:
                # This line is content for the currently active block
                # Preserve leading indentation but remove trailing newlines
                current_block_content_lines.append(line_with_newline.rstrip("\n"))
                idx += 1
            elif line_stripped:
                # Line has content but no block is active and it's not an expected marker
                raise ValueError(f"{function_name}: Unexpected content line: '{line_stripped}'. Expected a marker or end of input.")
            else:
                # Empty line when no block is active - ignore and continue
                idx += 1

        # Finalize the last active block after processing all lines
        if current_block_key:
            parameters[current_block_key] = "\n".join(current_block_content_lines).strip()

        # Validate that all expected block markers were found and processed
        if markers_to_find_stack:  # If stack is not empty, some required markers were missed
            raise ValueError(f"{function_name}: Missing expected block marker(s): {', '.join(markers_to_find_stack)}")

        # Ensure all expected parameters exist in the result, even if content was empty
        # This handles cases like "new_str:" at end of input with no content following
        for marker_key_no_colon in [m[:-1] for m in expected_block_markers_ordered]:
            if marker_key_no_colon not in parameters:
                # This case should ideally be caught by markers_to_find_stack check
                # But we ensure key exists if marker was found but had no content
                parameters[marker_key_no_colon] = ""  # Empty string for empty content

    # Parse test_report function: simple test command extraction
    elif function_name == "test_report":
        idx = 0
        while idx < len(lines_after_func_decl):
            line = lines_after_func_decl[idx].strip()
            if line.startswith("test_cmd:"):
                # Extract test command from current line or next line
                suf = line.removeprefix("test_cmd:")
                if suf:
                    # Command is on the same line as the marker
                    parameters["test_cmd"] = suf
                else:
                    # Command is on the next line
                    parameters["test_cmd"] = lines_after_func_decl[idx + 1].strip()
            idx += 1

        return {"function_name": function_name, "parameters": parameters}

    # Handle unknown function types
    else:
        raise ValueError(f"Unknown or unsupported function: {function_name}")

    # Return the parsed function call data
    return {"function_name": function_name, "parameters": parameters}
