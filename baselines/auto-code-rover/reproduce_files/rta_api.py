import subprocess
import os
import re

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
        elif inline_content_after_func and inline_content_after_func: # Inline content exists but it's not file_path
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
                content_on_marker_line = line_stripped[len(next_expected_marker_prefix):].strip()
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
        return {"function_name": function_name, "parameters": {}}
    
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
                timeout=600  # Add timeout (seconds)
            )
            timeout_occurred = False
        except subprocess.TimeoutExpired as e:
            # Handle timeout: collect available output
            process = e
            timeout_occurred = True

        result_str = f"EXECUTION RESULT of [execute_bash]:\n"
        stdout = getattr(process, "stdout", None)
        stderr = getattr(process, "stderr", None)
        # Collect stdout and stderr lines
        stdout_lines = stdout.splitlines(keepends=True) if stdout else []
        stderr_lines = stderr.splitlines(keepends=True) if stderr else []
        # Combine both for total line count
        combined_lines = stdout_lines + ([f"stderr:\n"] if stderr_lines else []) + stderr_lines
        # Truncate if total lines exceed 300
        truncated = False
        if len(combined_lines) > 300:
            combined_lines = combined_lines[:300]
            truncated = True
        # Reconstruct result_str
        result_str += ''.join(combined_lines)
        if not result_str.endswith('\n'):
            result_str += '\n'
        # Add truncation notice if needed
        if truncated:
            result_str += "[stderr] Output too long, only the first 300 lines are kept.\n"
        if timeout_occurred:
            result_str += "[The process was killed due to timeout (600 seconds).]\n"
            result_str += f"[Current working directory: {current_working_dir}]\n"
            result_str += "[Command finished with exit code: timeout]"
        else:
            result_str += f"[The command completed with exit code {process.returncode}.]\n"
            result_str += f"[Current working directory: {current_working_dir}]\n"
            result_str += f"[Command finished with exit code {process.returncode}]"
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
    The old_str must match exactly one location in the file.

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
        
        # Count occurrences of old_str
        occurrences = content.count(old_str)
        
        if occurrences == 0:
            return f"{result_prefix}Error: 'old_str' not found in file {file_path}."
        elif occurrences > 1:
            return f"{result_prefix}Error: 'old_str' found {occurrences} times in file {file_path}. Replacement requires exactly one match."
        
        # Exactly one occurrence, perform replacement
        modified_content = content.replace(old_str, new_str, 1) # Replace only the first (and only) occurrence
        _write_file_content(file_path, modified_content)
        
        return f"{result_prefix}Successfully replaced string in file: {file_path}"

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
                return "EXECUTION RESULT of [execute_bash]:\nError: 'cmd' parameter is missing."
            return api_execute_bash(params["cmd"])
        
        elif func_name == "str_replace":
            required_params = ["file_path", "old_str", "new_str"]
            for p_name in required_params:
                if p_name not in params:
                    return f"EXECUTION RESULT of [str_replace]:\nError: '{p_name}' parameter is missing."
            return api_str_replace(params["file_path"], params["old_str"], params["new_str"])
            
        elif func_name == "new_file":
            required_params = ["file_path", "new_str"]
            for p_name in required_params:
                if p_name not in params:
                    return f"EXECUTION RESULT of [new_file]:\nError: '{p_name}' parameter is missing."
            return api_new_file(params["file_path"], params["new_str"])
            
        elif func_name == "test_report":
            return 'RTA_FINISHED'
        else:
            # This case should ideally be caught by parse_api_call, but as a fallback:
            return f"EXECUTION RESULT of [unknown_function]:\nError: Unknown function '{func_name}'."

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
cmd:cd /workspace/clap_bug_reproduce && RUST_BACKTRACE=1 cargo build



    '''
    print(handle_api_call(cmd))
    