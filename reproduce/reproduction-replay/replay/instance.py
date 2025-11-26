"""
Instance definitions for different Software Engineering (SWE) agents.

This module provides concrete implementations of MultiSWEInstance for various SWE agents:
- MSWEAgentMultiSWEInstance: For SWE-agent trajectories
- OpenHandsMultiSWEInstance: For OpenHands (formerly OpenHands) trajectories
- RustAgentMultiSWEInstance: For RustAgent trajectories (extends OpenHands)

Each instance type handles trajectory parsing, LLM call extraction, and Docker
container management specific to its agent format.
"""

import json
from typing import Dict
from typing import List
from typing import Optional
from typing import override


from replay.container import OpenHandsDockerContainer
from replay.container import RustAgentDockerContainer
from replay.utils.docker_base import DockerContainer
from replay.utils.instance_base import MultiSWEInstance
from replay.utils.openhands import openhands_function_call_dumps


class MultiSWEInstanceMethod:
    """
    Constants for different MultiSWE instance method types.

    This class serves as an enumeration for supported SWE agent methods,
    providing string constants that identify each agent type.
    """

    OPENHANDS = "OpenHands"  # OpenHands (formerly OpenHands) agent
    RUSTAGENT = "RustAgent"  # RustAgent (Rust-specific) agent
    SWEAGENT = "SWE-agent"  # Multi-SWE agent


class SWEAgentMultiSWEInstance(MultiSWEInstance):
    """
    MultiSWEInstance implementation for SWE-agent trajectories.

    This class handles trajectory parsing for SWE-agent format, where trajectories
    are stored in a history array with optional demo flag markers. It separates
    demo trajectories from actual execution trajectories and provides LLM call
    extraction capabilities.
    """

    def __init__(
        self,
        instance_name: str,
        instance_model: str,
        instance_traj_path: str,
        instance_method: str = MultiSWEInstanceMethod.SWEAGENT,
    ):
        """
        Initialize MSWEAgent instance.

        Args:
            instance_name: Unique name identifier for the instance
            instance_model: Model name used by the agent
            instance_traj_path: Path to the trajectory file
            instance_method: Agent method type (defaults to MSWEAGENT)
        """
        super().__init__(
            instance_name=instance_name,
            instance_method=instance_method,
            instance_model=instance_model,
            instance_traj_path=instance_traj_path,
        )

    @override
    def __str__(
        self,
    ) -> str:
        """
        String representation of the instance.

        Returns:
            str: String describing the instance.
        """
        return f"MSWEAgentMultiSWEInstance(name={self.name}, model={self.model})"

    @override
    @property
    def full_trajs(
        self,
    ) -> List:
        """
        Get all non-demo trajectories from the SWE-agent history.

        Parses the trajectory file and extracts content from history entries
        that are not marked as demo trajectories.

        Returns:
            List: List of trajectory content strings
        """
        if not hasattr(self, "_full_trajs"):
            self._full_trajs = None
            try:
                with open(self.traj_path, "r") as f:
                    data = json.load(f)
                # Extract non-demo trajectories from history
                self._full_trajs = [h["content"] for h in data["history"] if "is_demo" not in h or not h["is_demo"]]
            except:
                raise
        return self._full_trajs

    @override
    @property
    def demo_trajs(self) -> List:
        """
        Get demo trajectories from the SWE-agent history.

        Parses the trajectory file and extracts content from history entries
        that are explicitly marked as demo trajectories.

        Returns:
            List: List of demo trajectory content strings
        """
        if not hasattr(self, "_demo_trajs"):
            self._demo_trajs = None
            try:
                with open(self.traj_path, "r") as f:
                    data = json.load(f)
                # Extract demo trajectories from history
                self._demo_trajs = [h["content"] for h in data["history"] if "is_demo" in h and h["is_demo"]]
            except:
                raise
        return self._demo_trajs

    @override
    @property
    def example_trajs(
        self,
    ) -> List:
        """
        Get the first two trajectories as example trajectories.

        Returns:
            List: First two trajectories from full_trajs
        """
        return self.full_trajs[:2]

    @override
    @property
    def llm_trajs(
        self,
    ) -> List:
        """
        Get all trajectories after the first two (which are examples).

        Returns:
            List: All trajectories except the first two
        """
        return self.full_trajs[2:]

    @override
    def get_llm_call_request_trajs(
        self,
    ) -> List[str]:
        """
        Get LLM call request trajectories (even-indexed trajectories).

        In SWE-agent format, LLM calls alternate between requests and responses.
        This method returns the even-indexed trajectories which represent requests.

        Returns:
            List[str]: List of LLM call request trajectories
        """
        return self.llm_trajs[::2]  # Every even index (0, 2, 4, ...)

    @override
    def get_llm_call_response_trajs(
        self,
    ) -> List[str]:
        """
        Get LLM call response trajectories (odd-indexed trajectories).

        In SWE-agent format, LLM calls alternate between requests and responses.
        This method returns the odd-indexed trajectories which represent responses.

        Returns:
            List[str]: List of LLM call response trajectories
        """
        return self.llm_trajs[1::2]  # Every odd index (1, 3, 5, ...)


class OpenHandsMultiSWEInstance(MultiSWEInstance):
    """
    MultiSWEInstance implementation for OpenHands (formerly OpenHands) trajectories.

    This class handles trajectory parsing for OpenHands format, which uses a messages
    array with roles (user/assistant) and supports both text content and tool calls.
    It processes complex message structures including function calls and multi-part content.
    """

    def __init__(
        self,
        instance_name: str,
        instance_model: str,
        instance_traj_path: str,
        instance_method: str = MultiSWEInstanceMethod.OPENHANDS,
    ):
        """
        Initialize OpenHands instance.

        Args:
            instance_name: Unique name identifier for the instance
            instance_model: Model name used by the agent
            instance_traj_path: Path to the trajectory file
            instance_method: Agent method type (defaults to OpenHands)
        """
        super().__init__(
            instance_name=instance_name,
            instance_method=instance_method,
            instance_model=instance_model,
            instance_traj_path=instance_traj_path,
        )

    @override
    def __str__(
        self,
    ) -> str:
        """
        String representation of the instance.

        Returns:
            str: String describing the instance.
        """
        return f"OpenHandsMultiSWEInstance(name={self.name}, model={self.model})"

    @override
    @property
    def full_trajs(
        self,
    ) -> List:
        """
        Parse and extract all trajectories from OpenHands message format.

        Processes the messages array, handling different content types:
        - String content: Added directly
        - List content: Text parts are concatenated, tool calls are appended
        - Skips duplicate consecutive user messages

        Returns:
            List: List of processed trajectory content strings
        """

        if not hasattr(self, "_full_trajs"):
            self._full_trajs = None
            try:
                with open(self.traj_path, "r") as f:
                    data = json.load(f)
                full_trajs = []
                prev_role = None
                for message in data["messages"]:
                    role = message["role"]
                    content = message["content"]
                    # Skip consecutive duplicate user messages
                    if prev_role == role and prev_role == "user":
                        continue
                    prev_role = role
                    if isinstance(content, str):
                        # Simple string content
                        full_trajs.append(content)
                    elif isinstance(content, list):
                        # Complex content with multiple parts
                        result = ""
                        for c in content:
                            assert "type" in c and c["type"] == "text", "No text found"
                            result += c["text"]
                        # Check for tool calls and append them
                        if "tool_calls" in message:
                            assert len(message["tool_calls"]) > 0, "No tool calls"
                            tool_call = message["tool_calls"][0]
                            assert "type" in tool_call and tool_call["type"] == "function" and "function" in tool_call, f"Tool call type is not function"
                            function = tool_call["function"]
                            assert "name" in function and "arguments" in function, "No function name or arguments found"
                            if result:
                                result += "\n"
                            # Append function call dump to result
                            result += openhands_function_call_dumps(
                                function["name"],
                                json.loads(function["arguments"]),
                            )
                        full_trajs.append(result)
                    else:
                        raise RuntimeError("Invalid trajectory format")
                self._full_trajs = full_trajs
            except:
                raise
        return self._full_trajs

    @override
    @property
    def example_trajs(
        self,
    ) -> Optional[List]:
        """
        Get the first two trajectories as example trajectories.

        Returns:
            Optional[List]: First two trajectories from full_trajs
        """
        return self.full_trajs[:2]

    @override
    @property
    def llm_trajs(
        self,
    ) -> List:
        """
        Get all trajectories after the first two (which are examples).

        Returns:
            List: All trajectories except the first two
        """
        return self.full_trajs[2:]

    @override
    def get_llm_call_request_trajs(
        self,
    ) -> List[str]:
        """
        Get LLM call request trajectories (even-indexed trajectories).

        In OpenHands format, LLM calls alternate between requests and responses.
        This method returns the even-indexed trajectories which represent requests.

        Returns:
            List[str]: List of LLM call request trajectories
        """
        return self.llm_trajs[::2]  # Every even index (0, 2, 4, ...)

    @override
    def get_llm_call_response_trajs(
        self,
    ) -> List[str]:
        """
        Get LLM call response trajectories (odd-indexed trajectories).

        In OpenHands format, LLM calls alternate between requests and responses.
        This method returns the odd-indexed trajectories which represent responses.

        Returns:
            List[str]: List of LLM call response trajectories
        """
        return self.llm_trajs[1::2]  # Every odd index (1, 3, 5, ...)

    def docker_container_context_manager(
        self,
    ) -> DockerContainer:
        """
        Get the Docker container context manager class for OpenHands.

        Returns:
            DockerContainer: The OpenHandsDockerContainer class
        """
        return OpenHandsDockerContainer

    def get_docker_image_name(
        self,
    ) -> str:
        """
        Generate the Docker image name for this OpenHands instance.

        Creates a standardized Docker image name based on the repository
        owner, name, and PR number in lowercase format.

        Returns:
            str: The Docker image name in format rustbench/{owner}/{repo}:pr-{pr_number}_runtime
        """
        return f"rustbench/{self.owner}__{self.repo}:pr-{self.pr_number}_runtime".lower()

    @property
    def workspace(self) -> str:
        """
        Get the workspace path for this OpenHands instance.

        Returns:
            str: Workspace path in format /workspace/{owner}__{repo}__{version}
        """
        return f"/workspace/{self.owner}__{self.repo}__{self.version}"


class RustAgentMultiSWEInstance(OpenHandsMultiSWEInstance):
    """
    MultiSWEInstance implementation for RustAgent trajectories.

    RustAgent extends OpenHands functionality with Rust-specific features.
    It uses a similar message format but with different trajectory structure:
    - Only first trajectory is example (vs 2 for OpenHands)
    - Supports both direct messages and nested history.messages format
    - Includes special methods for test report handling
    """

    def __init__(
        self,
        instance_name: str,
        instance_model: str,
        instance_traj_path: str,
        instance_method: str = MultiSWEInstanceMethod.RUSTAGENT,
    ):
        """
        Initialize RustAgent instance.

        Args:
            instance_name: Unique name identifier for the instance
            instance_model: Model name used by the agent
            instance_traj_path: Path to the trajectory file
            instance_method: Agent method type (defaults to RUSTAGENT)
        """
        super().__init__(
            instance_name=instance_name,
            instance_method=instance_method,
            instance_model=instance_model,
            instance_traj_path=instance_traj_path,
        )

    @override
    def __str__(
        self,
    ) -> str:
        """
        String representation of the instance.

        Returns:
            str: String describing the instance.
        """
        return f"RustAgentMultiSWEInstance(name={self.name}, model={self.model})"

    @override
    @property
    def full_trajs(
        self,
    ) -> List:
        """
        Parse and extract all trajectories from RustAgent message format.

        RustAgent supports two message format variations:
        1. Direct messages array: data["messages"]
        2. Nested format: data["history"]["messages"]

        This method tries both formats and extracts content from each message.

        Returns:
            List: List of trajectory content strings
        """

        def _get_messages(_data: Dict) -> List[Dict]:
            """
            Extract messages from RustAgent data structure.

            Tries multiple possible locations for messages array.

            Args:
                _data: Parsed JSON data from trajectory file

            Returns:
                List[Dict]: List of message dictionaries

            Raises:
                RuntimeError: If no messages are found in expected locations
            """
            try:
                return _data["messages"]  # Direct messages array
            except:
                pass
            try:
                return _data["history"]["messages"]  # Nested messages array
            except:
                pass
            raise RuntimeError("No messages found")

        if not hasattr(self, "_full_trajs"):
            self._full_trajs = None
            try:
                with open(
                    self.traj_path,
                    "r",
                ) as f:
                    messages = _get_messages(json.load(f))
                full_trajs = []
                # Extract content from each message
                for message in messages:
                    full_trajs.append(message["content"])
                self._full_trajs = full_trajs
            except:
                raise
        return self._full_trajs

    @override
    @property
    def example_trajs(
        self,
    ) -> List:
        """
        Get the first trajectory as example trajectory.

        RustAgent uses only the first trajectory as example (unlike OpenHands which uses 2).

        Returns:
            List: First trajectory from full_trajs
        """
        return self.full_trajs[:1]

    @override
    @property
    def llm_trajs(
        self,
    ) -> List:
        """
        Get all trajectories after the first one (which is the example).

        Returns:
            List: All trajectories except the first one
        """
        return self.full_trajs[1:]

    @override
    def docker_container_context_manager(
        self,
    ) -> DockerContainer:
        """
        Get the Docker container context manager class for RustAgent.

        Returns:
            DockerContainer: The RustAgentDockerContainer class
        """
        return RustAgentDockerContainer

    def get_non_test_report_call_request_trajs(
        self,
    ) -> List[str]:
        """
        Get all LLM call request trajectories except the last one (test report).

        RustAgent typically ends with a test report trajectory. This method
        returns all LLM trajectories except the final test report.

        Returns:
            List[str]: List of LLM trajectories excluding the test report
        """
        return self.llm_trajs[:-1]

    def get_test_report_traj(self) -> str:
        """
        Get the last trajectory, which contains the test report.

        RustAgent typically ends execution with a test report that summarizes
        the results of the code changes and tests executed.

        Returns:
            str: The last trajectory content (test report)
        """
        return self.llm_trajs[-1]


# Mapping of method names to their corresponding instance classes
_instance_method_class_map: Dict[str, type] = {
    MultiSWEInstanceMethod.OPENHANDS: OpenHandsMultiSWEInstance,
    MultiSWEInstanceMethod.RUSTAGENT: RustAgentMultiSWEInstance,
    MultiSWEInstanceMethod.SWEAGENT: SWEAgentMultiSWEInstance,
}


def make_mswe_instance(
    instance_id: str,
    instance_method: str,
    instance_model: str,
    instance_traj_path: str,
) -> MultiSWEInstance:
    """
    Factory function to create a MultiSWEInstance based on the specified method.

    This function validates the method type, creates the appropriate instance,
    and performs validation checks on the trajectory file.

    Args:
        instance_id: Unique identifier for the instance
        instance_method: The SWE agent method type (OPENHANDS, RUSTAGENT, or SWEAGENT)
        instance_model: The model name used by the agent
        instance_traj_path: Path to the trajectory file

    Returns:
        MultiSWEInstance: The created and validated instance

    Raises:
        NotImplementedError: If the method type is not supported
        RuntimeError: If instance creation fails or trajectory file is invalid
    """
    if instance_method not in _instance_method_class_map:
        raise NotImplementedError(f"Unknown method: {instance_method}")
    try:
        # Create instance using the appropriate class
        instance: MultiSWEInstance = _instance_method_class_map[instance_method](
            instance_name=instance_id_to_name(instance_id),
            instance_model=instance_model,
            instance_traj_path=instance_traj_path,
        )
    except Exception as e:
        raise RuntimeError(f"Unexpected error happened when make instance {instance_id}") from e
    try:
        # Validate that trajectory file can be loaded
        instance.full_trajs
    except Exception as e:
        raise RuntimeError(f"Traj file for {instance} is not exists") from e
    return instance


def instance_id_to_name(
    instance_id: str,
) -> str:
    """
    Convert an instance ID to an instance name by replacing the last dash with double underscores.

    This function finds the last occurrence of a dash in the instance ID and replaces
    it with double underscores to create the internal instance name format.

    Example:
        "repo-name-123" -> "repo-name__123"

    Args:
        instance_id: The instance ID with dashes

    Returns:
        str: The converted instance name with double underscores
    """
    last_dash_index = instance_id.rindex("-")
    return instance_id[:last_dash_index] + "__" + instance_id[last_dash_index + 1 :]


def instance_name_to_id(
    instance_name: str,
) -> str:
    """
    Convert an instance name to an instance ID by replacing the last double underscores with a dash.

    This function finds the last occurrence of double underscores in the instance name
    and replaces it with a single dash to create the external instance ID format.

    Example:
        "repo-name__123" -> "repo-name-123"

    Args:
        instance_name: The instance name with double underscores

    Returns:
        str: The converted instance ID with dashes
    """
    last_dash_index = instance_name.rindex("__")
    return instance_name[:last_dash_index] + "-" + instance_name[last_dash_index + 2 :]
