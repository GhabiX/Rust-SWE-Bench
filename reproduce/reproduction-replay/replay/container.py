"""
Docker container managers for different Software Engineering (SWE) agents.

This module provides Docker container implementations for various SWE agents:
- OpenHandsDockerContainer: Manages OpenHands (formerly OpenHands) containers
- RustAgentDockerContainer: Manages RustAgent containers (extends OpenHands)

Each container manager handles:
- Service startup and health checking
- API communication with the containerized agent
- Function call execution and trajectory replay
- Workspace preparation and environment setup
"""

import json
import os
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import requests

from replay.utils.decorator import func_retry
from replay.utils.docker_base import DockerClient
from replay.utils.docker_base import DockerContainer
from replay.utils.docker_base import DockerError
from replay.utils.error import error_single_line_message
from replay.utils.instance_base import MultiSWEInstance
from replay.utils.log import log_error
from replay.utils.log import log_info
from replay.utils.openhands import openhands_function_call_loads
from replay.utils.osex import os_free_port
from replay.utils.rustagent import rustagent_extract_function_calls
from replay.utils.rustagent import rustagent_function_call_loads


class OpenhandsDockerError(DockerError):
    """
    Custom exception class for OpenHands Docker-related errors.

    This exception is raised when OpenHands-specific Docker operations fail,
    such as API communication errors or service startup failures.
    """

    pass


class OpenHandsDockerContainer(DockerContainer):
    """
    Docker container manager for OpenHands agent.
    
    This class manages the lifecycle of OpenHands Docker containers, including:
    - Starting the container with proper environment and command configuration
    - Health checking and service readiness monitoring
    - API communication for executing commands and file operations
    - Workspace preparation and Git configuration
    - Function call parsing and execution from trajectories
    
    OpenHands runs as a web service inside the container, accessible via HTTP API.
    """

    def __init__(
        self,
        instance: MultiSWEInstance,
        host: Optional[str] = None,
        port: Optional[int] = None,
        init_commands: Optional[List[str]] = None,
        client: Optional[DockerClient] = None,
        *args,
        **kwargs,
    ):
        """
        Initialize OpenHands Docker container manager.

        Args:
            instance: MultiSWEInstance containing trajectory and configuration data
            host: Service host address (defaults to localhost)
            port: Service port (auto-assigned if None)
            init_commands: Optional list of initialization commands to run in container
            client: Optional Docker client instance
            *args: Additional positional arguments for parent DockerContainer
            **kwargs: Additional keyword arguments for parent DockerContainer
        """
        if host is None:
            host = "localhost"
        if port is None:
            port = os_free_port()  # Get a free port for the service

        self.host: str = host
        self.port: int = port
        self.instance: MultiSWEInstance = instance

        # Initialize parent DockerContainer with OpenHands-specific configuration
        super().__init__(
            client=client,
            image_name=instance.get_docker_image_name(),
            command=" ".join(
                [
                    "/openhands/micromamba/bin/micromamba",  # Micromamba environment manager
                    "run",
                    "-n",
                    "openhands",  # Use environment named "openhands"
                    "poetry",  # Use Poetry package manager
                    "run",
                    "python",  # Run Python
                    "-u",  # Unbuffered output for real-time logging
                    "-m",
                    "openhands.runtime.action_execution_server",  # Main service module
                    str(port),  # Service port
                    "--working-dir",  # Working directory flag
                    "/workspace",
                    "--username",  # Username flag
                    "root",  # Run as root user
                    "--user-id",  # User ID flag
                    "0",  # User ID 0 (root)
                ]
            ),
            *args,
            **kwargs,
        )
        self.init_commands: Optional[List[str]] = init_commands

    def _default_container_name(self) -> str:
        """
        Generate a default container name for OpenHands playback sessions.
        
        Creates a unique container name using instance name, timestamp, and random hex.
        
        Returns:
            str: Unique container name for this playback session
        """
        return f"openhands_playback__{self.instance.name}__{int(time.time())}__{os.urandom(4).hex()}"

    @property
    def functions(self) -> Dict[str,Any]:
        """
        Get the mapping of supported function names to their implementations.
        
        This property provides lazy initialization of the function mapping,
        which includes all supported container operations that can be called
        from trajectories.
        
        Returns:
            Dict[str, Any]: Mapping of function names to callable methods
        """
        if not hasattr(self, "_functions"):
            self._functions: Dict[str, Any] = {
                "execute_bash": self.execute_bash,      # Execute shell commands
                "str_replace_editor": self.str_replace_editor,  # File operations
            }
        return self._functions


    @func_retry(max_attempts=180, delay=10)
    def _wait_api_ready(self) -> None:
        """
        Wait for the OpenHands API service to become ready and responsive.
        
        This method polls the health endpoint until the service responds successfully.
        Uses exponential backoff with retry decorator for robustness.
        Total timeout: up to 30 minutes (180 attempts × 10 seconds).
        
        Raises:
            DockerError: If the service fails to become ready within timeout period
        """
        try:
            log_info(self.logger, f"⏳ Waiting for OpenHands service to start ...")
            response = requests.get(
                url=f"http://{self.host}:{self.port}/alive",  # Health check endpoint
            )
            response.raise_for_status()  # Raise exception for HTTP errors
            response = response.json()   # Parse JSON response
            log_info(self.logger, f"✅ OpenHands service is ready -- http://{self.host}:{self.port}")
        except Exception as e:
            raise DockerError(f"Failed to connect to OpenHands backend service -- {e}")

    def _prepare_workspace(self) -> None:
        """
        Prepare the working environment inside the container.
        
        This method performs essential setup tasks:
        1. Configure Git global user settings and add no-pager alias
        2. Move the code repository from /home to the workspace directory
        3. Change to the project working directory
        4. Display current user for debugging
        5. Execute any additional initialization commands
        
        All commands are executed sequentially and any failure will propagate up.
        """
        cmds: List[str] = [
            # Configure Git for clean operation
            f'git config --global user.name "openhands" && git config --global user.email "openhands@all-hands.dev" && alias git="git --no-pager"',
            # Move repository to workspace location
            f"mv /home/{self.instance.repo} {self.instance.workspace}",
            # Change to the working directory
            f"cd {self.instance.workspace}",
            # Display current user for debugging purposes
            f"whoami",
        ]
        # Add any custom initialization commands
        if self.init_commands:
            cmds.extend(self.init_commands)
        # Execute all commands in sequence
        for cmd in cmds:
            self.execute_bash(cmd)

    def __enter__(self) -> "OpenHandsDockerContainer":
        """
        Context manager entry point: start container and prepare environment.
        
        This method is called when entering a 'with' statement and performs:
        1. Start the Docker container
        2. Wait for the API service to become ready
        3. Prepare the workspace environment
        
        Returns:
            OpenHandsDockerContainer: The current instance for chaining
        """
        self.run()  # Start the Docker container
        self._wait_api_ready()  # Wait for service to be responsive
        self._prepare_workspace()  # Set up the working environment
        return self

    def execute_bash(
        self,
        command: str,
        **kwargs,
    ) -> Tuple[int, str]:
        """
        Execute a shell command inside the container via OpenHands API.
        
        This method sends a command execution request to the OpenHands service
        running inside the container. The command runs in blocking mode with
        full output capture.
        
        Args:
            command: The shell command string to execute
            **kwargs: Additional parameters (currently unused)
            
        Returns:
            Tuple[int, str]: (exit_code, output_content) where exit_code is the
                           command's return code and output_content is stdout/stderr
            
        Raises:
            OpenHandsDockerError: If API request fails or response parsing fails
        """
        try:
            log_info(self.logger, "-" * 100)
            log_info(self.logger, f"🔄 Executing command: {command}")
            
            # Send command execution request to OpenHands API
            data = requests.post(
                url=f"http://{self.host}:{self.port}/execute_action",
                json={
                    "action": {
                        "action": "run",
                        "args": {
                            "command": command,
                            "is_input": False,      # Not an interactive input
                            "thought": "",          # No thought annotation
                            "blocking": True,       # Wait for completion
                            "hidden": False,        # Don't hide output
                        },
                        "timeout": 3600,           # 1 hour timeout
                    },
                },
            ).json()
            
            # Validate response structure
            assert "success" in data, f"success not in response: {data}"
            assert "content" in data, f"content not in response: {data}"
            assert "extras" in data, f"extras not in response: {data}"
            assert "metadata" in data["extras"], f"metadata not in response: {data}"
            assert "exit_code" in data["extras"]["metadata"], f"exit_code not in response: {data}"
            
            # Log execution result
            if not data["success"]:
                log_error(self.logger, f"❌ Command execution failed: \n{json.dumps(data, indent=4)}")
            else:
                log_info(self.logger, "✅ Command executed successfully")
                
            # Extract result data
            content: str = data.get("content").strip()
            exit_code: int = data["extras"]["metadata"]["exit_code"]
            
            # Log output if present
            if content:
                log_info(self.logger, f"📄 Output:\n{content}")
            log_info(self.logger, "-" * 100)
            
            return exit_code, content
            
        except (requests.exceptions.RequestException, AssertionError) as e:
            error_msg = f"OpenHands backend service request error -- {error_single_line_message(e)}"
            log_error(self.logger, error_msg)
            raise OpenhandsDockerError(error_msg)

    def str_replace_editor(
        self,
        command: str,
        path: str,
        **kwargs,
    ) -> Tuple[int, str]:
        """
        Perform file read/write operations inside the container via OpenHands API.
        
        This method handles various file operations by sending requests to the
        OpenHands service. It supports both file viewing (read) and editing operations.
        
        Args:
            command: Operation command ("view" for reading, others for editing)
            path: File path to operate on
            **kwargs: Additional parameters for the API request (e.g., old_str, new_str)
            
        Returns:
            Tuple[int, str]: (exit_code, output_content) where exit_code indicates
                           success (1) or failure (0), and output_content contains
                           the operation result or error message
            
        Raises:
            OpenHandsDockerError: If API request fails or response parsing fails
        """
        try:
            log_info(self.logger, "-" * 100)
            log_info(self.logger, f"🔄 File operation: {command}, Path: {path}")
            log_info(self.logger, f"\tParams: {json.dumps(kwargs, indent=4)}")
            
            if command == "view":
                # File reading operation
                data = requests.post(
                    url=f"http://{self.host}:{self.port}/execute_action",
                    json={
                        "action": {
                            "action": "read",
                            "args": {
                                "path": path,
                                **kwargs,
                                "thought": "",
                                "security_risk": None,
                                "impl_source": "oh_aci",  # OpenHands action implementation
                            },
                        },
                    },
                ).json()
            else:
                # File editing operation (create, str_replace, etc.)
                data = requests.post(
                    url=f"http://{self.host}:{self.port}/execute_action",
                    json={
                        "action": {
                            "action": "edit",
                            "args": {
                                "command": command,
                                "path": path,
                                **kwargs,
                                "thought": "",
                                "security_risk": None,
                                "impl_source": "oh_aci",  # OpenHands action implementation
                            },
                        },
                    },
                ).json()
                
            # Validate response structure
            assert "content" in data, f"content not in response: {data}"
            
            # Determine exit code based on error status
            if data["content"].startswith("ERROR:"):
                exit_code = 1  # Failure
                log_error(self.logger, "❌ Command execution failed")
            else:
                exit_code = 0  # Success
                log_info(self.logger, "✅ Command executed successfully")
                
            # Extract and log content
            content: str = data.get("content").strip()
            if content:
                log_info(self.logger, f"📄 Output:\n{content}")
            log_info(self.logger, "-" * 100)
            
            return exit_code, content
            
        except (requests.exceptions.RequestException, AssertionError) as e:
            error_msg = f"OpenHands backend service request error -- {error_single_line_message(e)}"
            log_error(self.logger, error_msg)
            raise OpenhandsDockerError(error_msg)

    def call_function_from_traj(
        self,
        traj: str,
    ) -> Tuple[int, str]:
        """
        Parse and execute a function call from a OpenHands trajectory string.
        
        This method parses XML-formatted trajectory strings to extract function
        calls and their parameters, then dispatches to the appropriate handler.
        
        Args:
            traj: XML-formatted trajectory string containing function name and parameters
            
        Returns:
            Tuple[int, str]: Result tuple from the executed function
            
        Raises:
            DockerError: If function execution fails or parsing errors occur
        """
        try:
            # Parse the XML trajectory to extract function name and parameters
            name, kwargs = openhands_function_call_loads(traj)
            
            # Dispatch to the appropriate function if it exists
            if name in self.functions:
                return self.functions[name](**kwargs)
            else:
                log_error(self.logger, f"❌ Function {name} does not exist")
                return 127, "function not found"  # Command not found exit code
                
        except DockerError as e:
            log_error(self.logger, f"OpenHands backend service request error -- {error_single_line_message(e)}")
            raise e
        except Exception as e:
            log_error(self.logger, f"Unknown exception in container -- {error_single_line_message(e)}")
            raise DockerError(f"Unknown exception in container -- {error_single_line_message(e)}")


class RustAgentDockerContainer(OpenHandsDockerContainer):
    """
    Docker container manager for RustAgent, extending OpenHands functionality.
    
    RustAgent builds upon OpenHands but uses different function call formats
    and supports additional Rust-specific operations. This class:
    - Inherits OpenHands container management and API communication
    - Provides RustAgent-specific function parsing and execution
    - Supports file operations, bash execution, and test reporting
    - Handles RustAgent's custom trajectory format for function calls
    """

    def __init__(
        self,
        instance: MultiSWEInstance,
        host: Optional[str] = None,
        port: Optional[int] = None,
        init_commands: Optional[List[str]] = None,
        client: Optional[DockerClient] = None,
        *args,
        **kwargs,
    ):
        """
        Initialize RustAgent Docker container manager.
        
        Args:
            instance: MultiSWEInstance containing trajectory and configuration data
            host: Service host address (defaults to localhost)
            port: Service port (auto-assigned if None)
            init_commands: Optional list of initialization commands to run in container
            client: Optional Docker client instance
            *args: Additional positional arguments for parent class
            **kwargs: Additional keyword arguments for parent class
        """
        super().__init__(
            instance=instance,
            host=host,
            port=port,
            init_commands=init_commands,
            client=client,
            *args,
            **kwargs,
        )

    def _init_functions(self) -> None:
        """
        Initialize the function mapping for RustAgent container actions.
        
        Note: This method appears to be unused. The actual function mapping
        should be handled through the inherited `functions` property.
        """
        self.functions: Dict[str, Any] = {
            "execute_bash": self.execute_bash,
            "str_replace": self.str_replace_editor,
        }

    def rustagent_call_by_string(
        self,
        rta_call_string: str,
    ) -> Tuple[int, str]:
        """
        Parse and execute a RustAgent function call from a string representation.
        
        This method parses RustAgent's custom function call string format,
        extracts the function name and parameters, and dispatches the call.
        
        Args:
            rta_call_string: String representation of the function call
            
        Returns:
            Tuple[int, str]: (exit_code, output) from the executed function
        """
        try:
            # Parse the RustAgent function call string
            function = rustagent_function_call_loads(rta_call_string)
            name, params = function["function_name"], function["parameters"]
            return self.rustagent_call(name, params)
        except ValueError as e:
            log_error(self.logger, f"❌ Function call parsing error: {error_single_line_message(e)}")
            return -1, f"API PARSING ERROR:\n{error_single_line_message(e)}"
        except Exception as e:
            log_error(self.logger, f"❌ Unknown error: {error_single_line_message(e)}")
            return -1, f"UNEXPECTED DISPATCH ERROR:\n{error_single_line_message(e)}"

    def rustagent_call(
        self,
        function_name: str,
        function_params: Dict[str, Any],
    ) -> Tuple[int, str]:
        """
        Dispatch and execute a RustAgent function by name with parameters.
        
        This method handles the core RustAgent function types:
        - execute_bash: Execute shell commands
        - str_replace: Replace text in files
        - new_file: Create new files
        - test_report: Signal completion of test execution
        
        Args:
            function_name: Name of the function to execute
            function_params: Dictionary of parameters for the function
            
        Returns:
            Tuple[int, str]: (exit_code, output) from the executed function
        """
        if function_name == "execute_bash":
            # Execute shell command - requires 'cmd' parameter
            if "cmd" not in function_params:
                log_error(self.logger, f"❌ Missing function call parameter: cmd")
                return -1, "EXECUTION RESULT of [execute_bash]:\nError: 'cmd' parameter is missing."
            return self.execute_bash(
                command=function_params["cmd"],
            )
            
        elif function_name == "str_replace":
            # Replace text in file - requires file_path, old_str, new_str
            for param in ["file_path", "old_str", "new_str"]:
                if param not in function_params:
                    log_error(self.logger, f"❌ Missing function call parameter: {param}")
                    return -1, f"EXECUTION RESULT of [str_replace]:\nError: '{param}' parameter is missing."
            return self.str_replace_editor(
                command="str_replace",
                path=function_params["file_path"],
                old_str=function_params["old_str"],
                new_str=function_params["new_str"],
            )
            
        elif function_name == "new_file":
            # Create new file - requires file_path, new_str
            for param in ["file_path", "new_str"]:
                if param not in function_params:
                    log_error(self.logger, f"❌ Missing function call parameter: {param}")
                    return -1, f"EXECUTION RESULT of [new_file]:\nError: '{param}' parameter is missing."
            log_info(self.logger, f"🔄 Creating file with params: {function_params}")
            path = function_params["file_path"]
            # Ensure parent directory exists
            self.execute_bash(
                command=f'mkdir -p "{os.path.dirname(path)}"',
            )
            # Remove existing file if present
            self.execute_bash(command=f'rm -f "{path}"')
            # Create the new file
            return self.str_replace_editor(
                command="create",
                path=path,
                file_text=function_params["new_str"],
            )
            
        elif function_name == "test_report":
            # Test completion signal - no actual execution needed
            return 0, "RTA_FINISHED"
            
        else:
            # Unknown function
            log_error(self.logger, f"❌ Unknown function call: {function_name}")
            return -1, f"EXECUTION RESULT of [unknown_function]:\nError: Unknown function '{function_name}'."

    def call_function_from_traj(
        self,
        traj: str,
    ) -> Tuple[int, str]:
        """
        Parse and execute function calls from a RustAgent trajectory string.
        
        This method extracts function calls from RustAgent trajectory format
        and executes the first valid function call found. RustAgent trajectories
        may contain multiple function calls, but typically only the first is executed.
        
        Args:
            traj: RustAgent trajectory string containing function calls
            
        Returns:
            Tuple[int, str]: Result tuple from the executed function
            
        Raises:
            DockerError: If function execution fails or parsing errors occur
        """
        try:
            # Extract all function calls from the trajectory
            for call_string in rustagent_extract_function_calls(traj):
                # Execute the first function call found
                return self.rustagent_call_by_string(call_string)
            # No function calls found in trajectory
            log_error(self.logger, "No function call found in trajectory")
            return 127, "function not found"  # Command not found exit code
            
        except DockerError as e:
            log_error(self.logger, f"OpenHands backend service request error -- {error_single_line_message(e)}")
            raise e
        except Exception as e:
            log_error(self.logger, f"Unknown exception in container -- {error_single_line_message(e)}")
            raise DockerError(f"Unknown exception in container -- {error_single_line_message(e)}")