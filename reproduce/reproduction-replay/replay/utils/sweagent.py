"""
SWE-Agent utilities for trajectory replay and function call processing.

This module provides comprehensive utilities for working with SWE-Agent (Software
Engineering Agent), specifically the SWE-agent implementation. It handles:

- Function call formatting and command extraction from trajectories
- File creation and editing operations in SWE-Agent format
- Status information parsing from agent responses
- Trajectory replay execution and result processing
- Integration with the SWE-agent Docker-based execution environment

The module supports the complete workflow from trajectory preparation to execution
and result collection, enabling automated software engineering task replay and
evaluation using the SWE-Agent framework.

Key Features:
    - Function call formatting with markdown code blocks
    - Command extraction from multi-line trajectories
    - Status parsing (current file, directory) from agent responses
    - File creation with proper escaping and validation
    - Trajectory list management and manipulation
    - Complete replay execution with Docker container management
    - Result collection including logs, trajectories, and patches

Functions:
    - sweagent_function_call_dump: Format message and command as function call
    - sweagent_function_call_extract_command: Extract commands from trajectories
    - sweagent_function_response_*: Parse and manipulate agent responses
    - sweagent_create_file_dumps: Generate file creation command sequences
    - sweagent_trajs_*: Manage trajectory lists
    - sweagent_internal_*_commands: Get sets of internal SWE-Agent commands
    - sweagent_replay: Execute complete trajectory replay with result collection

Dependencies:
    - SWE-agent: Must be available in the dependency list
    - Docker: Required for container-based replay execution
    - subprocess: For running external SWE-Agent processes

Constants:
    - SWEAGENT_ROOT: Root directory of SWE-agent installation
    - SWEAGENT_INSTANCE_INFO_FILE_PATH: Path to instance information database
"""

import getpass
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Dict, List, Set
from typing import Optional
from typing import Tuple
from typing import Union

from replay.instance import MultiSWEInstanceMethod
from replay.instance import make_mswe_instance
from replay.utils.dependency import dependency_list
from replay.utils.dependency import dependency_root
from replay.utils.error import error_single_line_message
from replay.utils.instance_base import MultiSWEInstance
from replay.utils.text import text_remove_line_break

# Verify that SWE-agent is available as a dependency
assert "SWE-agent" in dependency_list(full_path=False)
# Root directory of the SWE-agent installation
SWEAGENT_ROOT = os.path.join(dependency_root(), "SWE-agent")
# Path to the instance information database file
SWEAGENT_INSTANCE_INFO_FILE_PATH = os.path.join(SWEAGENT_ROOT, "data", "rust_all.jsonl")


def sweagent_function_call_dump(
    message: str,
    command: str,
) -> str:
    """
    Format a message and command as a SWE-Agent function call block.

    Creates the standard SWE-Agent format for function calls, which consists of
    a natural language message followed by a command enclosed in markdown code blocks.
    This format is used throughout SWE-Agent trajectories for agent-environment interaction.

    Args:
        message: Natural language description or explanation of what the command does.
                This provides context and reasoning for the agent's action.
        command: The actual command to execute (bash command, editor command, etc.).
                Should not contain triple backticks as they would break the format.

    Returns:
        Formatted string in SWE-Agent function call format with message and code block

    Examples:
        >>> call = sweagent_function_call_dump("Create a new Python file", "create hello.py")
        >>> print(call)
        Create a new Python file

        ```
        create hello.py
        ```

        >>> call = sweagent_function_call_dump("Search for TODO comments", "search_dir 'TODO'")
        >>> print(call)
        Search for TODO comments

        ```
        search_dir 'TODO'
        ```

    Note:
        The output format is critical for SWE-Agent parsing. The message is separated
        from the command block by two newlines, and the command is enclosed in
        markdown code blocks (triple backticks).
    """
    return f"{message}\n\n```\n{command}\n```"


def sweagent_function_call_extract_command(
    trajectory: str,
) -> Optional[str]:
    """
    Extract the last non-empty command from a SWE-Agent trajectory string.

    Parses a trajectory string to find all code blocks and returns the last one
    that contains an actual command (non-empty content after the language identifier).
    This is useful for getting the most recent command executed in a trajectory.

    Args:
        trajectory: The trajectory string containing multiple function calls and
                   responses. May contain multiple code blocks with commands.

    Returns:
        The last non-empty command found in the trajectory, or None if no valid
        commands are found or if the trajectory is empty.

    Examples:
        >>> traj = '''Agent message

        ```
        create file.py
        ```

        Response content

        ```
        edit 1:5
        print("hello")
        ```'''
        >>> cmd = sweagent_function_call_extract_command(traj)
        >>> print(cmd)
        edit 1:5
        print("hello")

        >>> # Empty trajectory returns None
        >>> sweagent_function_call_extract_command("")
        None

    Processing Logic:
        1. Find all markdown code blocks in the trajectory (```...```)
        2. Parse each block to separate language identifier from command content
        3. Skip blocks that have content in the language identifier line
        4. Return the last block with actual command content
        5. Return None if no valid commands found

    Note:
        The function processes blocks in reverse order to find the most recent
        command efficiently, and filters out empty or invalid command blocks.
    """
    if not trajectory:
        return None

    # Find all code blocks in the trajectory using regex with DOTALL flag
    # Pattern captures: (language_identifier, command_content)
    code_blocks = re.findall(
        r"\n```(.*?)\n(.*?)\n```",
        trajectory,
        re.DOTALL,
    )

    # Process blocks in reverse order to find the last valid command
    for command in reversed(code_blocks):
        # Skip blocks where the first line (language identifier) has content
        # We want blocks where the language identifier line is empty
        if command[0].strip():
            continue
        # Return the command content (second capture group) if it's non-empty
        command_content = command[1].strip()
        if command_content:
            return command_content

    return None


# Compiled regex pattern for extracting SWE-Agent status information
# Matches the format: (Open file: filename)(Current directory: path)bash-prompt$
_sweagent_status_pattern = re.compile(r"\n\(Open file: (.*?)\)\n\(Current directory: (.*?)\)\nbash.*$")


def sweagent_function_response_remove_status(
    content: str,
) -> str:
    """
    Remove the status block from SWE-Agent response content.

    SWE-Agent responses often end with a status block showing the currently
    open file and working directory. This function removes that status information
    to get the clean command output or response content.

    Args:
        content: The raw response content from SWE-Agent that may contain
                status information at the end

    Returns:
        The content with the status block removed. If no status block is found,
        returns the original content unchanged.

    Examples:
        >>> content = '''Command output here
        ... More output
        ... (Open file: /path/to/file.py)
        ... (Current directory: /workspace)
        ... bash-5.0$'''
        >>> clean = sweagent_function_response_remove_status(content)
        >>> print(clean)
        Command output here
        More output

        >>> # Content without status block is returned unchanged
        >>> sweagent_function_response_remove_status("Just regular output")
        'Just regular output'

    Status Block Format:
        The status block typically appears at the end of responses and follows
        the pattern: (Open file: filename)(Current directory: path)bash-prompt

    Note:
        This function uses regex substitution to remove the entire status block.
        It's safe to call on content that doesn't have a status block.
    """
    # Use the pre-compiled regex pattern to remove status blocks
    return re.sub(
        _sweagent_status_pattern,
        "",  # Replace with empty string to remove the status block
        content,
    )


def sweagent_function_response_extract_status(
    content: str,
) -> Tuple[str, str]:
    """
    Extract the open file and current directory from SWE-Agent response content.

    Parses the status block at the end of SWE-Agent responses to extract
    the currently open file and working directory. This information is
    useful for tracking the agent's state during trajectory execution.

    Args:
        content: The response content that should contain a status block
                with file and directory information

    Returns:
        Tuple containing (open_file_path, current_directory_path).
        If multiple status blocks exist, returns information from the last one.

    Raises:
        RuntimeError: If the content does not contain a valid status block
                     with the expected format

    Examples:
        >>> content = '''Command executed successfully
        ... (Open file: /workspace/src/main.py)
        ... (Current directory: /workspace/src)
        ... bash-5.0$'''
        >>> open_file, current_dir = sweagent_function_response_extract_status(content)
        >>> print(f"File: {open_file}, Dir: {current_dir}")
        File: /workspace/src/main.py, Dir: /workspace/src

        >>> # Invalid content raises error
        >>> sweagent_function_response_extract_status("No status here")
        RuntimeError: Content is not a valid sweagent content: No status here

    Status Block Format:
        Expected format: (Open file: path)(Current directory: path)bash-prompt
        The function extracts the two path components from this structured format.

    Note:
        If multiple status blocks exist in the content, the function returns
        the information from the last (most recent) status block found.
    """
    # Find all status blocks in the content using the pre-compiled pattern
    results = _sweagent_status_pattern.findall(content)
    if not results:
        raise RuntimeError(f"Content is not a valid sweagent content: {content}")

    # Return the last status block found (most recent state)
    return results[-1]


def sweagent_create_file_dumps(
    dst_file_path_in_container: str,
    content: str,
    message: Optional[str] = None,
) -> List[str]:
    """
    Generate SWE-Agent command sequence for creating a file with content.

    Creates a sequence of SWE-Agent function calls to create a new file and
    populate it with content. This involves two steps: creating the empty file
    and then editing it to add the content. The function ensures content
    safety by validating that it doesn't contain markdown code block markers.

    Args:
        dst_file_path_in_container: Path where the file should be created inside
                                  the SWE-Agent container environment
        content: The text content to write to the file. Must not contain
                lines starting with triple backticks (```) as they would
                break the SWE-Agent command format.
        message: Optional descriptive message for the file creation operation.
                If None, uses a default automated message.

    Returns:
        List of two formatted SWE-Agent function call strings:
        1. File creation command (create "filename")
        2. File editing command (edit 1:1 with content)

    Raises:
        ValueError: If the content contains lines starting with triple backticks (```)
                   which would break the SWE-Agent command format

    Examples:
        >>> commands = sweagent_create_file_dumps(
        ...     "/workspace/hello.py",
        ...     'print("Hello, World!")',
        ...     "Create greeting script"
        ... )
        >>> for cmd in commands:
        ...     print(cmd)
        ...     print("---")
        Create greeting script

        ```
        create "/workspace/hello.py"
        ```
        ---
        Create greeting script

        ```
        edit 1:1
        print("Hello, World!")
        end_of_edit
        ```

        >>> # Content with code blocks raises error
        >>> sweagent_create_file_dumps("/path", "```python\ncode\n```", "message")
        ValueError: content which contains r'^```' is not allowed in SWE-agent

    Command Sequence:
        1. create "filepath" - Creates an empty file at the specified path
        2. edit 1:1...end_of_edit - Edits the file to insert the content

    Safety Note:
        The content validation is critical because SWE-Agent uses markdown
        code blocks to delimit commands, so embedded triple backticks would
        break the command parsing.
    """
    # Validate content doesn't contain markdown code block markers
    if re.search(r"^```", content, re.MULTILINE):
        raise ValueError("content which contains r'^```' is not allowed in SWE-agent")

    # Use provided message or default automated message
    message = message or "[AUTOMATED FILE CREATION MESSAGE]"

    # Return sequence of two commands: create file, then edit with content
    return [
        f'{message}\n\n```\ncreate "{dst_file_path_in_container}"\n```',
        f"{message}\n\n```\nedit 1:1\n{content}\nend_of_edit\n```",
    ]


def sweagent_trajs_add_command(
    sweagent_replay_trajs: List[Dict],
    message: str,
    command: str,
) -> None:
    """
    Add a formatted command to a SWE-Agent trajectory list.

    Convenience function to append a properly formatted SWE-Agent function call
    to a trajectory list. The function call is formatted using the standard
    message + code block format and added to the provided list.

    Args:
        sweagent_replay_trajs: List of trajectory elements to append to.
                              Modified in-place by adding the new command.
        message: Natural language description of what the command does
        command: The actual command to execute

    Returns:
        None (modifies the trajectory list in-place)

    Examples:
        >>> trajs = []
        >>> sweagent_trajs_add_command(trajs, "List files", "ls -la")
        >>> print(len(trajs))  # 1
        >>> print(trajs[0])
        List files

        ```
        ls -la
        ```

    Note:
        This is a helper function that combines trajectory list management
        with function call formatting for convenience.
    """
    # Format the command and add it to the trajectory list
    sweagent_replay_trajs.append(
        sweagent_function_call_dump(
            message=message,
            command=command,
        )
    )


def sweagent_trajs_create_file(
    sweagent_replay_trajs: List[Dict],
    file_path: str,
    content: str,
    message: Optional[str] = None,
) -> None:
    """
    Add file creation commands to a SWE-Agent trajectory list.

    Convenience function to add the complete sequence of commands needed to
    create a file with content to a trajectory list. This extends the list
    with both the file creation and content editing commands.

    Args:
        sweagent_replay_trajs: List of trajectory elements to extend.
                              Modified in-place by adding file creation commands.
        file_path: Path where the file should be created in the container
        content: Text content to write to the file
        message: Optional descriptive message. If None, uses default message.

    Returns:
        None (modifies the trajectory list in-place)

    Examples:
        >>> trajs = []
        >>> sweagent_trajs_create_file(
        ...     trajs,
        ...     "/workspace/test.py",
        ...     'print("test")',
        ...     "Create test file"
        ... )
        >>> print(len(trajs))  # 2 (create + edit commands)

    Note:
        This function adds multiple commands to the trajectory list - one for
        file creation and one for content editing. It's a convenience wrapper
        around sweagent_create_file_dumps().
    """
    # Generate file creation command sequence and extend the trajectory list
    sweagent_replay_trajs.extend(
        sweagent_create_file_dumps(
            dst_file_path_in_container=file_path,
            content=content,
            message=message,
        )
    )


def sweagent_internal_unedit_commands() -> Set[str]:
    """
    Get the set of SWE-Agent commands that don't modify file content.

    Returns a set of internal SWE-Agent commands that are used for navigation,
    searching, and viewing but don't actually edit or modify files. These are
    often called "read-only" or "non-editing" commands.

    Returns:
        Set of command names that don't modify files:
        - goto: Navigate to a specific line in a file
        - scroll_down: Scroll down in the current file view
        - scroll_up: Scroll up in the current file view
        - search_dir: Search for text/patterns in directory
        - search_file: Search for text/patterns in current file
        - find_file: Find files by name or pattern

    Examples:
        >>> commands = sweagent_internal_unedit_commands()
        >>> print("goto" in commands)  # True
        >>> print("edit" in commands)  # False

    Use Cases:
        - Filtering trajectory commands by type
        - Analyzing agent behavior (navigation vs. modification)
        - Replay optimization (skip non-modifying commands)
        - Command categorization for analysis

    Note:
        These commands are considered "safe" in that they don't change
        the state of files in the workspace, only the agent's view.
    """
    return set(
        [
            "goto",  # Navigate to specific line number
            "scroll_down",  # Scroll down in file view
            "scroll_up",  # Scroll up in file view
            "search_dir",  # Search text in directory
            "search_file",  # Search text in current file
            "find_file",  # Find files by name/pattern
        ]
    )


def sweagent_internal_total_commands() -> Set[str]:
    """
    Get the complete set of internal SWE-Agent commands.

    Returns a set containing all supported internal SWE-Agent commands,
    including both file modification and navigation/search commands.
    These are the built-in commands that the SWE-Agent understands
    natively, as opposed to arbitrary bash commands.

    Returns:
        Set of all internal SWE-Agent command names:
        - File operations: open, create, edit, submit
        - Navigation: goto, scroll_down, scroll_up
        - Search: search_dir, search_file, find_file

    Examples:
        >>> all_commands = sweagent_internal_total_commands()
        >>> print(len(all_commands))  # 10
        >>> print("edit" in all_commands)  # True
        >>> print("custom_command" in all_commands)  # False

    Command Categories:
        - File Management: open, create, edit, submit
        - Navigation: goto, scroll_down, scroll_up
        - Search: search_dir, search_file, find_file

    Use Cases:
        - Validating command names in trajectories
        - Distinguishing internal commands from bash commands
        - Command completion and validation
        - Analysis of agent command usage patterns

    Note:
        This represents the complete vocabulary of SWE-Agent's internal
        command system. Commands not in this set are treated as external
        bash commands to be executed in the shell.
    """
    return set(
        [
            # File management commands
            "open",  # Open a file for editing
            "create",  # Create a new empty file
            "edit",  # Edit file content at specific lines
            "submit",  # Submit the solution/changes
            # Navigation commands
            "goto",  # Go to specific line number
            "scroll_down",  # Scroll down in file view
            "scroll_up",  # Scroll up in file view
            # Search commands
            "search_dir",  # Search for text in directory
            "search_file",  # Search for text in current file
            "find_file",  # Find files by name or pattern
        ]
    )


def _sweagent_replay_id(
    instance: MultiSWEInstance,
    lang: str = "rust",
) -> str:
    """
    Generate a unique replay identifier for a SWE-Agent instance.

    Creates a standardized identifier string used for naming replay-related
    files and directories. The ID combines the language and instance ID
    to ensure uniqueness across different replay sessions.

    Args:
        instance: The MultiSWE instance being replayed
        lang: Programming language identifier (default: "rust")

    Returns:
        Formatted replay ID string in the format "{lang}_{instance.id}"

    Examples:
        >>> instance = MultiSWEInstance("rust-lang__rust__123", ...)
        >>> replay_id = _sweagent_replay_id(instance)
        >>> print(replay_id)  # "rust_rust-lang__rust-123"

        >>> replay_id = _sweagent_replay_id(instance, "python")
        >>> print(replay_id)  # "python_rust-lang__rust-123"

    Use Cases:
        - Naming temporary files during replay
        - Creating unique directory names
        - Identifying replay sessions in logs
        - Mapping instances to their replay results

    Note:
        This is an internal helper function used by other replay-related
        functions. The generated ID should be unique within a replay session.
    """
    return f"{lang}_{instance.id}"


def _sweagent_replay_find_result_dir(
    instance: MultiSWEInstance,
    lang: str = "rust",
) -> Optional[str]:
    """
    Find the result directory for a completed SWE-Agent replay.

    Searches the SWE-Agent trajectories directory for the result directory
    created during replay execution. The directory name contains the replay ID
    and is located in a user-specific subdirectory.

    Args:
        instance: The MultiSWE instance that was replayed
        lang: Programming language identifier used in replay (default: "rust")

    Returns:
        Absolute path to the result directory if found, None otherwise.
        The directory contains trajectory files, patches, and other replay outputs.

    Examples:
        >>> instance = MultiSWEInstance("rust-lang__rust__123", ...)
        >>> result_dir = _sweagent_replay_find_result_dir(instance)
        >>> if result_dir:
        ...     print(f"Results at: {result_dir}")
        ... else:
        ...     print("No results found")

    Directory Structure:
        The function searches in: {SWEAGENT_ROOT}/trajectories/{username}/
        For directories containing: "replay__{replay_id}"

    Search Process:
        1. Construct the trajectory directory path using current username
        2. List all subdirectories in the trajectory directory
        3. Find directories with names containing the replay ID pattern
        4. Return the absolute path of the first match found

    Use Cases:
        - Locating replay results after execution
        - Collecting output files and patches
        - Cleanup and result processing
        - Debugging replay execution issues

    Note:
        This function depends on SWE-Agent's directory naming conventions.
        Returns None if no matching directory is found, which may indicate
        replay failure or incomplete execution.
    """
    # Construct path to user's trajectory directory
    traj_dir_path = os.path.join(SWEAGENT_ROOT, "trajectories", getpass.getuser())

    # Generate the replay ID to search for
    replay_id = _sweagent_replay_id(instance=instance, lang=lang)

    # Search for directories containing the replay ID
    for replay_result_dir_name in os.listdir(traj_dir_path):
        if f"replay__{replay_id}" in replay_result_dir_name:
            # Return absolute path to the first matching directory
            return os.path.abspath(os.path.join(traj_dir_path, replay_result_dir_name))

    return None


def sweagent_replay(instance: MultiSWEInstance, replay_trajs: List[str], lang: str = "rust", timeout: Optional[float] = None) -> Tuple[str, str, Optional[str]]:
    """
    Execute a complete SWE-Agent replay process with trajectory execution.

    This function orchestrates the full replay pipeline for a SWE-Agent instance,
    including environment setup, trajectory execution, and result collection.
    It creates a temporary workspace, configures the replay environment, executes
    the provided trajectories, and returns comprehensive execution results.

    Args:
        instance: MultiSWE instance object containing instance metadata and ID.
                  Must be of type MSWEAGENT and have a valid instance ID that
                  exists in the SWE-Agent instance database.
        replay_trajs: List of trajectory strings to execute during replay.
                     Each string represents a sequence of commands to execute
                     in the SWE-Agent environment.
        lang: Programming language identifier for environment setup.
              Affects container configuration and tool availability (default: "rust").
        timeout: Maximum execution time in seconds for the replay process.
                If None, uses system default timeout (default: None).

    Returns:
        Tuple containing:
            - replay_log (str): Complete execution log with stdout/stderr output
            - replay_result (str): Trajectory execution result from .traj file
            - replay_patch (Optional[str]): Generated patch file content if available,
              None if no patch was created during execution

    Raises:
        RuntimeError: When replay execution fails, including:
            - Instance not found in SWE-Agent database
            - Subprocess execution failures or timeouts
            - Missing result directories after execution
            - File system or permission errors
        AssertionError: When instance method is not MSWEAGENT

    Examples:
        Basic Replay:
        >>> instance = MultiSWEInstance.load("rust-lang__rust__123")
        >>> trajectories = ["edit file.rs", "submit solution"]
        >>> log, result, patch = sweagent_replay(instance, trajectories)
        >>> print(f"Execution successful: {len(result)} chars")

        With Timeout:
        >>> log, result, patch = sweagent_replay(
        ...     instance, trajectories, timeout=1800.0
        ... )
        >>> if patch:
        ...     print(f"Generated patch: {len(patch)} lines")

        Error Handling:
        >>> try:
        ...     log, result, patch = sweagent_replay(instance, trajectories)
        ... except RuntimeError as e:
        ...     print(f"Replay failed: {e}")

    Execution Process:
        1. Validation: Verify instance type and existence in database
        2. Temporary Workspace: Create isolated directory for execution
        3. Instance Configuration: Extract and prepare instance metadata
        4. Trajectory Setup: Write trajectories to action file
        5. SWE-Agent Execution: Run replay subprocess with configuration
        6. Result Collection: Gather logs, trajectories, and patches
        7. File Processing: Read and return all execution outputs
        8. Cleanup: Remove temporary files and directories

    File Structure Created:
        - {replay_id}.jsonl: Instance configuration file
        - {replay_id}_actions.jsonl: Trajectory commands file
        - {replay_id}_logs.log: Complete execution log
        - result/: Directory containing:
            - {instance_id}.traj: Execution trajectory
            - patches/{instance_id}.patch: Generated patch (if any)

    Subprocess Configuration:
        The function executes SWE-Agent's run.py with:
        - config/default.yaml: Standard configuration
        - install_environment=True: Fresh environment setup
        - model_name=replay: Special replay execution mode
        - max_workers_build_image=1: Sequential image building
        - cache_task_images=True: Docker image caching enabled

    Performance Considerations:
        - Docker container setup adds significant overhead (~30-60 seconds)
        - Large trajectories may require increased timeout values
        - Temporary directory cleanup is automatic via context manager
        - Result directory is moved to prevent conflicts

    Integration Points:
        - MultiSWEInstance: Primary data source and validation
        - SWE-Agent run.py: Core execution engine
        - Docker containers: Isolated execution environment
        - File system: Trajectory storage and result management

    Use Cases:
        - Automated reproduction of agent behaviors
        - Batch processing of trajectory datasets
        - Research data collection and analysis
        - Debugging and validation of agent outputs
        - Performance benchmarking and optimization

    Note:
        This function requires a properly configured SWE-Agent environment
        with Docker support and all necessary dependencies installed.
        The instance must exist in the SWE-Agent instance database file.
    """
    # Validate that instance is compatible with SWE-Agent replay
    assert instance.method == MultiSWEInstanceMethod.SWEAGENT, f"instance {instance} is not {MultiSWEInstanceMethod.SWEAGENT}"

    # Create temporary directory for all replay operations
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"sweagent replay in temp directory '{temp_dir}'")

        # Locate the main SWE-Agent instance database file
        all_instance_info_file_path = SWEAGENT_INSTANCE_INFO_FILE_PATH
        replay_instance_info_file_path = os.path.join(temp_dir, f"{_sweagent_replay_id(instance=instance, lang=lang)}.jsonl")

        # Search for the specific instance in the database
        replay_instance_info = None
        with open(all_instance_info_file_path) as f:
            for line in f.readlines():
                instance_info = json.loads(line)
                if instance_info["instance_id"] == instance.id:
                    replay_instance_info = instance_info
                    break

        # Ensure the instance was found in the database
        if replay_instance_info is None:
            raise RuntimeError(f"Instance {instance.id} not found in {all_instance_info_file_path}")

        # Write instance configuration to temporary file
        with open(replay_instance_info_file_path, "w") as f:
            json.dump(replay_instance_info, f)

        # Create action file containing the trajectories to replay
        replay_instance_action_file_path = os.path.join(temp_dir, f"{_sweagent_replay_id(instance=instance, lang=lang)}_actions.jsonl")
        with open(replay_instance_action_file_path, "w") as f:
            json.dump(
                {
                    instance.id: replay_trajs,
                },
                f,
            )

        # Configure SWE-Agent subprocess arguments
        args = [
            "python",
            os.path.join(SWEAGENT_ROOT, "run.py"),
            "--config_file",
            "config/default.yaml",
            "--pr_file",
            replay_instance_info_file_path,
            "--install_environment",
            "True",
            "--model_name",
            "replay",
            "--replay_path",
            replay_instance_action_file_path,
            "--print_config",
            "False",
            "--max_workers_build_image",
            "1",
            "--remove_image",
            "False",
            "--cache_task_images",
            "False",
        ]

        # Create log file for capturing all subprocess output
        replay_log_file_path = os.path.join(temp_dir, f"{_sweagent_replay_id(instance=instance, lang=lang)}_logs.log")

        # Execute the SWE-Agent replay subprocess
        with open(replay_log_file_path, "w") as f:
            try:
                subprocess.run(
                    args,
                    check=True,
                    cwd=SWEAGENT_ROOT,
                    stdout=f,
                    stderr=f,
                    timeout=timeout,
                )

            except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
                raise RuntimeError(f"replay subprocess error {instance.id} -- {error_single_line_message(e)} -- {text_remove_line_break(e.stderr.decode() + e.stdout.decode())}")
            except Exception as e:
                raise RuntimeError(f"replay unexpected error {instance.id} -- {error_single_line_message(e)}")

        # Locate and move the result directory to temporary workspace
        replay_result_dir_path: Optional[str] = _sweagent_replay_find_result_dir(instance=instance, lang=lang)
        if not replay_result_dir_path:
            raise RuntimeError(f"replay failed, no result directory found")
        shutil.move(replay_result_dir_path, os.path.join(temp_dir, "result"))
        replay_result_dir_path = os.path.join(temp_dir, "result")

        # Read the complete execution log
        with open(replay_log_file_path, "r") as f:
            replay_log = f.read()

        # Read the trajectory execution result
        replay_result_file_path = os.path.join(replay_result_dir_path, f"{instance.id}.traj")
        with open(replay_result_file_path, "r") as f:
            replay_result = f.read()

        # Read the generated patch file if it exists
        replay_patch_file_path = os.path.join(replay_result_dir_path, "patches", f"{instance.id}.patch")
        if os.path.exists(replay_patch_file_path):
            with open(replay_patch_file_path, "r") as f:
                replay_patch = f.read()
        else:
            replay_patch = None

        # Return all collected results
        return replay_log, replay_result, replay_patch
