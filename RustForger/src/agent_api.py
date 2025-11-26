import subprocess
import os
import re
import json

# Constants
MAX_OUTPUT_LINES = 300
BASH_TIMEOUT_SECONDS = 600

# New configuration constants for smarter truncation
MAX_HEAD_LINES = 200  # Number of lines to keep from the beginning
MAX_TAIL_LINES = 100  # Number of lines to keep from the end

def parse_api_call(call_string: str) -> dict:
    """
    Parses the custom API call string into a function name and parameters dictionary.

    The format is as follows:
    - `function:<name>` is on the first line.
      - Optional: the first parameter (e.g. `cmd:`, `file_path:`) can be on this same line.
    - For `execute_bash`:
        - `cmd:<command_first_line>` is expected either inline with `function:execute_bash`
          or on the immediately following line.
        - Subsequent lines after the line containing `cmd:` are part of the multi-line command.
          Content can also start on the same line as `cmd:`.
    - For `str_replace` and `new_file`:
        - `file_path:<path>` is expected either inline with `function:name` or on the
          immediately following line.
        - Subsequent block markers (`old_str:`, `new_str:`) are expected on their own lines,
          or content can start on the same line as the marker.
        - Content for these blocks can span multiple lines.

    Args:
        call_string: The raw string representing the API call.

    Returns:
        A dictionary with "function_name" and "parameters" keys.

    Raises:
        ValueError: If the call_string is malformed or required parameters are missing.
    """
    raw_lines_with_newlines = call_string.strip().splitlines(True)
    if not raw_lines_with_newlines:
        raise ValueError("API call string cannot be empty.")

    first_line_full = raw_lines_with_newlines.pop(0) # Consume the first line
    first_line_stripped = first_line_full.strip()
    
    func_match = re.match(r"function:(\w+)", first_line_stripped)
    if not func_match:
        raise ValueError("API call must start with 'function:<name>'.")
    
    function_name = func_match.group(1)
    parameters = {}

    # Content remaining on the function line itself, after "function:name"
    inline_content_after_func = first_line_stripped[func_match.end():].strip()

    # `remaining_lines_for_params` are lines after the `function:` line, WITH their original newlines
    # This list will be consumed (popped from) as parameters are parsed.
    lines_after_func_decl = list(raw_lines_with_newlines) 

    if function_name == "execute_bash":
        cmd_line_content = None # This will be the stripped line containing "cmd:" prefix and its value
        
        if inline_content_after_func.startswith("cmd:"):
            cmd_line_content = inline_content_after_func
            # All lines in `lines_after_func_decl` are subsequent content for the command
        elif lines_after_func_decl and lines_after_func_decl[0].strip().startswith("cmd:"):
            cmd_line_content = lines_after_func_decl.pop(0).strip() # Consume cmd line
            # Remaining lines in `lines_after_func_decl` are subsequent content
        else:
            raise ValueError("execute_bash: 'cmd:' parameter prefix is missing or malformed. It should be inline with 'function:execute_bash' or on the next line.")
        
        cmd_content_parts = []
        # Extract content from the "cmd:" line itself
        content_on_cmd_line = cmd_line_content[len("cmd:"):].strip()
        if content_on_cmd_line:
            cmd_content_parts.append(content_on_cmd_line)
        
        # Append subsequent lines (these are already consumed from `lines_after_func_decl` if cmd: was on next line)
        for line_with_nl in lines_after_func_decl:
            cmd_content_parts.append(line_with_nl.rstrip('\n')) # Preserve leading spaces, remove trailing \n
        
        parameters["cmd"] = "\n".join(cmd_content_parts).strip()
        # An empty command string (e.g., "cmd:" followed by nothing) is allowed.

    elif function_name in ("new_file", "str_replace"):
        # 1. Parse file_path (must be the first parameter for these functions)
        file_path_line_content = None # Stripped line content for file_path:
        if inline_content_after_func.startswith("file_path:"):
            file_path_line_content = inline_content_after_func
            # `lines_after_func_decl` are for subsequent blocks (old_str/new_str)
        elif inline_content_after_func: # Inline content exists but it's not file_path
             raise ValueError(f"{function_name}: Unexpected inline content '{inline_content_after_func}'. Expected 'file_path:' or nothing.")
        elif lines_after_func_decl and lines_after_func_decl[0].strip().startswith("file_path:"):
            file_path_line_content = lines_after_func_decl.pop(0).strip() # Consume file_path line
        else:
            raise ValueError(f"{function_name}: 'file_path:' parameter is missing. It should be inline with 'function:{function_name}' or on the next line.")

        parameters["file_path"] = file_path_line_content[len("file_path:"):].strip()
        if not parameters["file_path"]:
            raise ValueError(f"{function_name}: 'file_path' value cannot be empty.")

        # 2. Parse subsequent blocks (old_str, new_str)
        expected_block_markers_ordered = []
        if function_name == "str_replace":
            expected_block_markers_ordered = ["old_str:", "new_str:"]
        elif function_name == "new_file":
            expected_block_markers_ordered = ["new_str:"] # Content for new_file is under new_str:
        
        # This mutable list will have markers popped as they are found
        markers_to_find_stack = list(expected_block_markers_ordered) 
        
        current_block_key = None       # e.g., "old_str" (without colon)
        current_block_content_lines = [] # Lines of content for the active block

        # Iterate through the *rest* of the lines for block markers
        # `lines_after_func_decl` now starts AFTER file_path line (if it was separate from function line)
        idx = 0
        while idx < len(lines_after_func_decl):
            line_with_newline = lines_after_func_decl[idx]
            line_stripped = line_with_newline.strip()

            next_expected_marker_prefix = markers_to_find_stack[0] if markers_to_find_stack else None
            
            if next_expected_marker_prefix and line_stripped.startswith(next_expected_marker_prefix):
                if current_block_key: # Finalize previous block's content
                    parameters[current_block_key] = "\n".join(current_block_content_lines)
                
                markers_to_find_stack.pop(0) # Consume this marker from the expected stack
                current_block_key = next_expected_marker_prefix[:-1] # Store key without colon (e.g., "new_str")
                current_block_content_lines = [] # Reset for new block

                # Content for this new block might start on this same line (after the marker)
                # FIX: remove strip() for keeping the original line structure
                content_on_marker_line = line_stripped[len(next_expected_marker_prefix):]
                # content_on_marker_line = line_stripped[len(next_expected_marker_prefix):].strip()
                if content_on_marker_line:
                    current_block_content_lines.append(content_on_marker_line)
                idx += 1 # Move to the next line
            elif current_block_key: # This line is content for the currently active block
                current_block_content_lines.append(line_with_newline.rstrip('\n')) # Preserve leading indents
                idx += 1
            elif line_stripped: # Line has content, not an expected marker, and no block is active
                raise ValueError(f"{function_name}: Unexpected content line: '{line_stripped}'. Expected a marker or end of input.")
            else: # Empty line, not part of an active block's content at this point, ignore.
                idx += 1
        
        # Finalize the last active block after the loop
        if current_block_key:
            parameters[current_block_key] = "\n".join(current_block_content_lines)

        # Validate all expected block markers were found and thus processed
        if markers_to_find_stack: # If stack is not empty, some markers were missed
            raise ValueError(f"{function_name}: Missing expected block marker(s): {', '.join(markers_to_find_stack)}")
        
        # Ensure that once a marker was found, its key exists in parameters (even if content was empty, e.g. "new_str:" then EOF)
        for marker_key_no_colon in [m[:-1] for m in expected_block_markers_ordered]:
            if marker_key_no_colon not in parameters:
                # This case should ideally be caught by `markers_to_find_stack` check if marker was entirely missing.
                # If marker was last line with no content, it should be ""
                parameters[marker_key_no_colon] = "" # Ensure key exists if marker was last and empty

    elif function_name == "test_report":
        # Parse test_report parameters with multi-line support
        expected_block_markers_ordered = ["test_cmd:", "test_file_path:", "test_analysis:", "reproduce_success:"]
        markers_to_find_stack = list(expected_block_markers_ordered)
        
        current_block_key = None
        current_block_content_lines = []
        
        # Check if first parameter is inline
        if inline_content_after_func:
            for marker in expected_block_markers_ordered:
                if inline_content_after_func.startswith(marker):
                    current_block_key = marker[:-1]  # Remove colon
                    content_on_marker_line = inline_content_after_func[len(marker):].strip()
                    if content_on_marker_line:
                        current_block_content_lines.append(content_on_marker_line)
                    markers_to_find_stack.remove(marker)
                    break
        
        # Process remaining lines
        idx = 0
        while idx < len(lines_after_func_decl):
            line_with_newline = lines_after_func_decl[idx]
            line_stripped = line_with_newline.strip()
            
            # Check if this line starts with a new marker
            found_marker = False
            for marker in markers_to_find_stack:
                if line_stripped.startswith(marker):
                    # Finalize previous block
                    if current_block_key:
                        parameters[current_block_key] = "\n".join(current_block_content_lines).strip()
                    
                    # Start new block
                    current_block_key = marker[:-1]  # Remove colon
                    current_block_content_lines = []
                    markers_to_find_stack.remove(marker)
                    
                    # Check if content starts on same line
                    content_on_marker_line = line_stripped[len(marker):].strip()
                    if content_on_marker_line:
                        current_block_content_lines.append(content_on_marker_line)
                    
                    found_marker = True
                    break
            
            if not found_marker and current_block_key:
                # This line is content for current block
                current_block_content_lines.append(line_with_newline.rstrip('\n'))
            
            idx += 1
        
        # Finalize last block
        if current_block_key:
            parameters[current_block_key] = "\n".join(current_block_content_lines).strip()

    elif function_name == "task_report":
        # Parse task_report parameters with multi-line support  
        expected_block_markers_ordered = ["task_modify_files:", "task_analysis:", "task_resolve_success:"]
        markers_to_find_stack = list(expected_block_markers_ordered)
        
        current_block_key = None
        current_block_content_lines = []
        
        # Check if first parameter is inline
        if inline_content_after_func:
            for marker in expected_block_markers_ordered:
                if inline_content_after_func.startswith(marker):
                    current_block_key = marker[:-1]  # Remove colon
                    content_on_marker_line = inline_content_after_func[len(marker):].strip()
                    if content_on_marker_line:
                        current_block_content_lines.append(content_on_marker_line)
                    markers_to_find_stack.remove(marker)
                    break
        
        # Process remaining lines
        idx = 0
        while idx < len(lines_after_func_decl):
            line_with_newline = lines_after_func_decl[idx]
            line_stripped = line_with_newline.strip()
            
            # Check if this line starts with a new marker
            found_marker = False
            for marker in markers_to_find_stack:
                if line_stripped.startswith(marker):
                    # Finalize previous block
                    if current_block_key:
                        parameters[current_block_key] = "\n".join(current_block_content_lines).strip()
                    
                    # Start new block
                    current_block_key = marker[:-1]  # Remove colon
                    current_block_content_lines = []
                    markers_to_find_stack.remove(marker)
                    
                    # Check if content starts on same line
                    content_on_marker_line = line_stripped[len(marker):].strip()
                    if content_on_marker_line:
                        current_block_content_lines.append(content_on_marker_line)
                    
                    found_marker = True
                    break
            
            if not found_marker and current_block_key:
                # This line is content for current block
                current_block_content_lines.append(line_with_newline.rstrip('\n'))
            
            idx += 1
        
        # Finalize last block
        if current_block_key:
            parameters[current_block_key] = "\n".join(current_block_content_lines).strip()

    elif function_name == "trace":
        # Parse trace parameters with multi-line support
        expected_single_markers = ["test_project:", "target_project:", "output:", "exec:"]
        expected_multi_markers = ["instrument:"]  # This can appear multiple times
        
        current_block_key = None
        current_block_content_lines = []
        
        # Initialize instrument list
        parameters["instrument"] = []
        
        # Check if first parameter is inline
        if inline_content_after_func:
            for marker in expected_single_markers + expected_multi_markers:
                if inline_content_after_func.startswith(marker):
                    current_block_key = marker[:-1]  # Remove colon
                    content_on_marker_line = inline_content_after_func[len(marker):].strip()
                    if content_on_marker_line:
                        if marker == "instrument:":
                            parameters["instrument"].append(content_on_marker_line)
                        else:
                            parameters[current_block_key] = content_on_marker_line
                    break
        
        # Process remaining lines
        idx = 0
        while idx < len(lines_after_func_decl):
            line_with_newline = lines_after_func_decl[idx]
            line_stripped = line_with_newline.strip()
            
            # Check if this line starts with a new marker
            found_marker = False
            for marker in expected_single_markers + expected_multi_markers:
                if line_stripped.startswith(marker):
                    # Get content on marker line
                    content_on_marker_line = line_stripped[len(marker):].strip()
                    
                    if marker == "instrument:":
                        # Handle multiple instrument entries
                        if content_on_marker_line:
                            parameters["instrument"].append(content_on_marker_line)
                    else:
                        # Handle single-value parameters
                        if content_on_marker_line:
                            parameters[marker[:-1]] = content_on_marker_line
                    
                    found_marker = True
                    break
            
            if not found_marker:
                # This line doesn't start with a marker, skip it or handle as needed
                pass
            
            idx += 1
    
    else:
        raise ValueError(f"Unknown or unsupported function: {function_name}")

    return {"function_name": function_name, "parameters": parameters}

def _ensure_dir_exists(file_path: str):
    """
    Ensures the directory for the given file_path exists, creating it if necessary.
    """
    dir_name = os.path.dirname(file_path)
    if dir_name: # Only attempt to create if there's a directory part
        os.makedirs(dir_name, exist_ok=True)

def _read_file_content(file_path: str) -> str:
    """
    Reads file content.
    Raises FileNotFoundError if file does not exist.
    Raises IsADirectoryError if path is a directory.
    Raises IOError for other read errors.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.path.isfile(file_path):
        raise IsADirectoryError(f"Path is a directory, not a file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise IOError(f"Error reading file {file_path}: {str(e)}")

def _write_file_content(file_path: str, content: str):
    """
    Writes content to a file, overwriting if it exists, creating if it doesn't.
    Raises IOError for write errors.
    """
    try:
        _ensure_dir_exists(file_path)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        raise IOError(f"Error writing to file {file_path}: {str(e)}")


# --- API Implementations ---

def api_execute_bash(command: str) -> str:
    """
    Executes a bash command and returns its output.
    This implementation is similar to the user's provided example.

    Args:
        command: The bash command to execute.

    Returns:
        A string detailing the execution result, including stdout, stderr, and exit code.
    """
    try:
        current_working_dir = os.getcwd()
        try:
            process = subprocess.run(
                command,
                shell=True,  # Be cautious with shell=True if commands come from untrusted sources
                cwd=current_working_dir,
                capture_output=True,
                text=True,
                check=False,  # Do not raise an exception for non-zero exit codes
                timeout=BASH_TIMEOUT_SECONDS  # Add timeout (seconds)
            )
            timeout_occurred = False
        except subprocess.TimeoutExpired as e:
            # Handle timeout: collect available output
            process = e
            timeout_occurred = True

        result_str = f"EXECUTION RESULT of [execute_bash]:\n"
        stdout = getattr(process, "stdout", None)
        stderr = getattr(process, "stderr", None)
        
        # Convert bytes to string if necessary (especially for timeout cases)
        if stdout is not None and isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if stderr is not None and isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
            
        # Collect stdout and stderr lines
        stdout_lines = stdout.splitlines(keepends=True) if stdout else []
        stderr_lines = stderr.splitlines(keepends=True) if stderr else []
        # Combine both for total line count
        combined_lines = stdout_lines + ([f"stderr:\n"] if stderr_lines else []) + stderr_lines
        
        # Smart truncation: if total lines exceed limit, keep first 200 and last 100 lines
        truncated = False
        total_lines = len(combined_lines)
        if total_lines > MAX_OUTPUT_LINES:
            # Calculate number of lines to be omitted
            omitted_lines = total_lines - MAX_HEAD_LINES - MAX_TAIL_LINES
            if omitted_lines > 0:
                # Keep first MAX_HEAD_LINES and last MAX_TAIL_LINES
                head_lines = combined_lines[:MAX_HEAD_LINES]
                tail_lines = combined_lines[-MAX_TAIL_LINES:]
                # Add truncation notice
                truncation_notice = [f"\n... [Truncated {omitted_lines} lines of output] ...\n\n"]
                combined_lines = head_lines + truncation_notice + tail_lines
                truncated = True
            else:
                # If total lines don't significantly exceed, use original truncation
                combined_lines = combined_lines[:MAX_OUTPUT_LINES]
                truncated = True
        
        # Reconstruct result_str
        result_str += ''.join(combined_lines)
        if not result_str.endswith('\n'):
            result_str += '\n'
        # Add truncation notice if needed
        if truncated:
            if total_lines > MAX_HEAD_LINES + MAX_TAIL_LINES:
                result_str += f"[Info] Output too long ({total_lines} lines), kept first {MAX_HEAD_LINES} and last {MAX_TAIL_LINES} lines.\n"
            else:
                result_str += f"[Info] Output too long, only the first {MAX_OUTPUT_LINES} lines are kept.\n"
        if timeout_occurred:
            result_str += f"[The process was killed due to timeout ({BASH_TIMEOUT_SECONDS} seconds).]\n"
            result_str += f"[Current working directory: {current_working_dir}]\n"
            result_str += "[Command finished with exit code: timeout]"
        else:
            result_str += f"[Current working directory: {current_working_dir}\n"
            result_str += f"Command finished with exit code: {process.returncode}]"
        return result_str

    except Exception as e:
        return (
            f"EXECUTION RESULT of [execute_bash]:\n"
            f"Python Exception during command execution: {str(e)}\n"
            f"[The command failed to execute due to an internal error.]"
        )


def api_str_replace(file_path: str, old_str: str, new_str: str) -> str:
    """
    Replaces a specific string segment in an existing file.
    Supports fuzzy matching by ignoring leading whitespace differences.

    Args:
        file_path: Absolute path to the file to modify.
        old_str: The exact string segment to be replaced.
        new_str: The new string segment to replace old_str.

    Returns:
        A string confirming success or detailing an error.
    """
    result_prefix = "EXECUTION RESULT of [str_replace]:\n"
    try:
        content = _read_file_content(file_path)
        
        # 1. Try exact matching first (maintain backward compatibility)
        if old_str in content:
            occurrences = content.count(old_str)
            if occurrences > 1:
                return f"{result_prefix}Funtion Error: 'old_str' found {occurrences} times in file {file_path}. Replacement requires exactly one match."
            
            # Exactly one occurrence, perform replacement
            modified_content = content.replace(old_str, new_str, 1)
            _write_file_content(file_path, modified_content)
            return f"{result_prefix}Successfully replaced string in file: {file_path}"
        
        # 2. Fuzzy matching: ignore leading whitespace on each line
        def strip_leading_spaces(text):
            """Remove leading whitespace from each line while preserving line structure"""
            return '\n'.join(line.lstrip() for line in text.split('\n'))
        
        # Normalize content by removing leading spaces
        fuzzy_content = strip_leading_spaces(content)
        fuzzy_old = strip_leading_spaces(old_str)
        fuzzy_new = strip_leading_spaces(new_str)
        
        # Check if fuzzy match exists and is unique
        if fuzzy_old in fuzzy_content:
            fuzzy_occurrences = fuzzy_content.count(fuzzy_old)
            if fuzzy_occurrences > 1:
                return f"{result_prefix}Funtion Error: 'old_str' found {fuzzy_occurrences} times in file {file_path} (fuzzy match). Replacement requires exactly one match."
            
            # Perform fuzzy replacement
            result_content = fuzzy_content.replace(fuzzy_old, fuzzy_new, 1)
            _write_file_content(file_path, result_content)
            return f"{result_prefix}Successfully replaced string in file: {file_path} (fuzzy match - leading whitespace ignored)"
        
        # Neither exact nor fuzzy match found
        return f"{result_prefix}Funtion Error: 'old_str' not found in file {file_path}."
        
    except (FileNotFoundError, IsADirectoryError, IOError) as e:
        return f"{result_prefix}Error processing file {file_path}: {str(e)}"
    except Exception as e:
        return f"{result_prefix}An unexpected error occurred: {str(e)}"

def api_new_file(file_path: str, new_str: str) -> str:
    """
    Creates a new file with specified content or overwrites an existing file.

    Args:
        file_path: Absolute path where the file will be created or overwritten.
        new_str: The entire content to be written into the file.

    Returns:
        A string confirming success or detailing an error.
    """
    result_prefix = "EXECUTION RESULT of [new_file]:\n"
    try:
        # Determine if it's a create or overwrite for the message, though _write_file_content handles both
        action = "created"
        if os.path.exists(file_path):
            action = "overwritten"
            
        _write_file_content(file_path, new_str)
        return f"{result_prefix}File {action} successfully at: {file_path}"
    except (IOError, OSError) as e: # OSError for path issues like invalid name
        return f"{result_prefix}Error operating on file {file_path}: {str(e)}"
    except Exception as e:
        return f"{result_prefix}An unexpected error occurred: {str(e)}"

def api_test_report(params: dict) -> dict:
    """
    Generates a test report with the provided parameters.
    
    Args:
        params: Dictionary containing test report parameters including:
            - test_cmd: Commands used for testing
            - test_file_path: Path to the test file
            - test_analysis: Analysis of the test results
            - reproduce_success: Boolean indicating if the issue was reproduced
    
    Returns:
        The test_report dictionary containing the 4 required fields.
    """
    test_cmd = params.get("test_cmd", "")
    test_file_path = params.get("test_file_path", "")
    test_analysis = params.get("test_analysis", "")
    reproduce_success = params.get("reproduce_success", "False")
    
    return {
        "test_cmd": test_cmd,
        "test_file_path": test_file_path,
        "test_analysis": test_analysis,
        "reproduce_success": reproduce_success
    }

def get_file_diff(file_path):
    """Get git diff for a file, simplified version"""
    if not os.path.exists(file_path):
        return "File does not exist"
    
    try:
        # Get absolute path and directory of the file
        abs_file_path = os.path.abspath(file_path)
        file_dir = os.path.dirname(abs_file_path)
        
        # Find git repository root directory
        git_root = file_dir
        while git_root != "/" and not os.path.exists(os.path.join(git_root, ".git")):
            git_root = os.path.dirname(git_root)
        
        if git_root == "/" or not os.path.exists(os.path.join(git_root, ".git")):
            # Not in a git repository, use git diff --no-index
            diff_result = subprocess.run(
                f"git diff --no-index /dev/null {abs_file_path}",
                shell=True, capture_output=True, text=True, check=False
            )
            if diff_result.stdout:
                return diff_result.stdout
            else:
                # If git diff --no-index also fails, read file content directly
                try:
                    with open(abs_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return f"New file (no git repository):\n{content}"
                except Exception:
                    return "New file but cannot read content"
        
        # In git repository, get relative path
        rel_path = os.path.relpath(abs_file_path, git_root)
        
        # Execute git status in git repository root directory
        status_result = subprocess.run(
            f"cd {git_root} && git status --porcelain -- {rel_path}",
            shell=True, capture_output=True, text=True, check=False
        )
        
        if status_result.returncode != 0:
            return f"Error running git status: {status_result.stderr}"
        
        status = status_result.stdout.strip()
        if not status:
            # File is tracked but has no changes
            return "No changes detected by git (file is tracked but unchanged)"
        elif status.startswith("??"):
            # New file (untracked)
            diff_result = subprocess.run(
                f"cd {git_root} && git diff --no-index /dev/null {rel_path}",
                shell=True, capture_output=True, text=True, check=False
            )
            if diff_result.stdout:
                return diff_result.stdout
            else:
                # Alternative: read file content directly
                try:
                    with open(abs_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return f"New file created:\n{content}"
                except Exception:
                    return "New file but cannot read content"
        else:
            # Tracked file with changes, use regular git diff
            diff_result = subprocess.run(
                f"cd {git_root} && git diff -- {rel_path}",
                shell=True, capture_output=True, text=True, check=False
            )
            if diff_result.stdout:
                return diff_result.stdout
            else:
                return "No changes detected by git"
            
    except Exception as e:
        return f"Error obtaining diff: {str(e)}"

def api_task_report(params: dict) -> dict:
    """
    Generates a task report with git diff information for modified files.
    
    Args:
        params: Dictionary containing task report parameters including:
            - task_modify_files: Path of modified files (comma-separated if multiple)
            - task_analysis: Analysis of the changes made
            - task_resolve_success: Boolean indicating if the task was successfully resolved
    
    Returns:
        The task_report dictionary containing the task information and diffs.
    """
    # Extract task parameters from input
    task_modify_files = params.get("task_modify_files", "")
    task_analysis = params.get("task_analysis", "")
    task_resolve_success = params.get("task_resolve_success", "False")
    
    # Create dictionary for final report
    task_report = {
        "task_modify_files": task_modify_files,
        "task_analysis": task_analysis,
        "task_resolve_success": task_resolve_success,
        "task_modify_files_diff": {}
    }

    # clean trace config
    process = subprocess.run(
        f"trace_cli clean -d /workspace",
        shell=True,
        capture_output=True,
        text=True,
        check=False
    )
    
    # Get git diff for each modified file
    if task_modify_files:
        modified_files = [f.strip() for f in task_modify_files.split(",")]
        for file_path in modified_files:
            task_report["task_modify_files_diff"][file_path] = get_file_diff(file_path)
    
    # Return the report dictionary
    return task_report

def api_trace(params: dict) -> str:
    """
    Executes the trace_cli run-flow command with the provided parameters.
    
    Args:
        params: Dictionary containing trace parameters including:
            - test_project: Path to the test project directory
            - target_project: Path to the target project directory  
            - instrument: List of instrumentation entries (file_path:function_name format)
            - output: Path for the output trace file
            - exec: Command to be executed in the test project
    
    Returns:
        A string detailing the execution result.
    """
    result_prefix = "EXECUTION RESULT of [trace]:\n"
    
    try:
        # Extract parameters
        test_project = params.get("test_project", "")
        target_project = params.get("target_project", "")
        instrument_list = params.get("instrument", [])
        output = params.get("output", "")
        exec_cmd = params.get("exec", "")
        
        # Validate required parameters
        if not test_project:
            return f"{result_prefix}Funtion Error: 'test_project' parameter is required."
        if not target_project:
            return f"{result_prefix}Funtion Error: 'target_project' parameter is required."
        if not instrument_list:
            return f"{result_prefix}Funtion Error: At least one 'instrument' parameter is required."
        if not output:
            return f"{result_prefix}Funtion Error: 'output' parameter is required."
        if not exec_cmd:
            return f"{result_prefix}Funtion Error: 'exec' parameter is required."
        
        # Build the trace_cli run-flow command
        cmd_parts = [
            "trace_cli", "run-flow",
            "--test-project", test_project,
            "--target-project", target_project
        ]
        
        # Add instrument arguments
        for instrument in instrument_list:
            cmd_parts.extend(["--instrument", instrument])
        
        # Add output and exec arguments
        cmd_parts.extend(["--output", output])
        cmd_parts.extend(["--exec", f'"{exec_cmd}"'])
        
        # Add clean flag
        cmd_parts.append("--clean --force")
        cmd_parts.append("--trace-tool-path /RTAgent/rustforger-tracer")
        cmd_parts.append(f" && head -30 {output}")
        
        # Join command parts
        full_command = " ".join(cmd_parts)
        # full_command += f" && head -30 {output}"

        # print(full_command)
        
        # Execute the command
        return api_execute_bash(full_command)
        
    except Exception as e:
        return f"{result_prefix}An unexpected error occurred: {str(e)}"


# --- Main Dispatcher (Example Usage) ---
def handle_api_call(call_string: str) -> str:
    """
    Parses an API call string and dispatches to the appropriate API function.
    """
    call_string = escape_backslashes_in_quoted_strings(call_string)
    try:
        parsed_call = parse_api_call(call_string)
        func_name = parsed_call["function_name"]
        params = parsed_call["parameters"]

        if func_name == "execute_bash":
            if "cmd" not in params:
                return "EXECUTION RESULT of [execute_bash]:\nFuntion Error: 'cmd' parameter is missing."
            return api_execute_bash(params["cmd"])
        
        elif func_name == "str_replace":
            required_params = ["file_path", "old_str", "new_str"]
            for p_name in required_params:
                if p_name not in params:
                    return f"EXECUTION RESULT of [str_replace]:\nFuntion Error: '{p_name}' parameter is missing."
            return api_str_replace(params["file_path"], params["old_str"], params["new_str"])
            
        elif func_name == "new_file":
            required_params = ["file_path", "new_str"]
            for p_name in required_params:
                if p_name not in params:
                    return f"EXECUTION RESULT of [new_file]:\nFuntion Error: '{p_name}' parameter is missing."
            return api_new_file(params["file_path"], params["new_str"])
            
        elif func_name == "test_report":
            report = api_test_report(params)
            return json.dumps(report)
        elif func_name == "task_report":
            report = api_task_report(params)
            return json.dumps(report)
        elif func_name == "trace":
            return api_trace(params)
        else:
            # This case should ideally be caught by parse_api_call, but as a fallback:
            return f"EXECUTION RESULT of [unknown_function]:\nFuntion Error: Unknown function '{func_name}'."

    except ValueError as e: # Catch parsing errors
        return f"API PARSING ERROR:\n{str(e)}"
    except Exception as e: # Catch any other unexpected errors during dispatch
        return f"UNEXPECTED DISPATCH ERROR:\n{str(e)}"


def escape_backslashes_in_quoted_strings(text):
    pattern = re.compile(r'(?<!["|\'])(".*?")|(\'.*?\')(?!["|\']*)', re.DOTALL)
    def replacer(match):
        quoted_string = match.group(0)
        return quoted_string.replace('\n', '\\n')
    return pattern.sub(replacer, text)

if __name__ == "__main__":
    os.system("clear")
    cmd = '''


function:test_report
test_cmd: 
cd /workspace/tokio-rs__bytes__0.1 && cargo run --example range_argument_example
test_file_path: 
/workspace/tokio-rs__bytes__0.1/examples/range_argument_example.rs
test_analysis: 
The attempt to run the example failed due to a dependency (`byteorder`) manifest issue with an unsupported edition (`2021`). Toolchain updates were unsuccessful, preventing resolution of the issue within this environment.
reproduce_success: 
False


    '''
    print(handle_api_call(cmd))
    