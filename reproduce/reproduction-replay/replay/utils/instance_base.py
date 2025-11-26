"""
Base class definitions for MultiSWE (Multi Software Engineering) instances.

This module provides the foundational MultiSWEInstance class that represents
software engineering tasks derived from GitHub pull requests. It serves as
an abstract base class for different SWE agent implementations, providing
common functionality for:

- Instance identification and metadata management
- GitHub pull request integration
- Trajectory data access (abstract properties)
- Dataset version management from rustbench
- LLM interaction trajectory tracking (abstract methods)

The class is designed to work with the rustbench dataset and provides a
standardized interface for accessing instance data and trajectories.

Classes:
    MultiSWEInstance: Abstract base class for SWE task instances

Constants:
    MULTISWE_DATASET_NAME: Dataset identifier for rustbench on Hugging Face
"""

import os
from typing import List
from typing import Optional
from typing import Tuple

from datasets import load_dataset

# Dataset name on Hugging Face Hub for rustbench instances
MULTISWE_DATASET_NAME = "user2f86/rustbench"


class MultiSWEInstance:
    """
    Abstract base class for MultiSWE instances representing GitHub pull request tasks.

    This class encapsulates software engineering tasks derived from GitHub pull requests,
    providing a standardized interface for accessing instance metadata, trajectories,
    and performing LLM-based operations. Each instance represents a specific pull request
    that can be used for training or evaluating software engineering agents.

    The class provides version information from the rustbench dataset and defines
    abstract properties and methods that must be implemented by concrete subclasses
    for different SWE agent frameworks.

    Attributes:
        name: Full instance name in format "owner__repo__pr_number"
        owner: GitHub repository owner/organization name
        repo: GitHub repository name
        pr_number: Pull request number as string
        id: Formatted instance ID for dataset lookup (owner__repo-pr_number)
        pr_link: Direct URL to the GitHub pull request
        method: Method/approach used for this instance
        model: LLM model name used for processing
        traj_path: Path to trajectory data files

    Abstract Properties:
        full_trajs: Complete trajectory data (must be implemented by subclasses)
        example_trajs: Example trajectory data (must be implemented by subclasses)
        llm_trajs: LLM-specific trajectory data (must be implemented by subclasses)

    Abstract Methods:
        get_llm_call_request_trajs(): Must be implemented by subclasses
        get_llm_call_response_trajs(): Must be implemented by subclasses
    """

    def __init__(
        self,
        instance_name: str,
        instance_method: str,
        instance_model: str,
        instance_traj_path: str,
    ):
        """
        Initialize a MultiSWE instance with metadata and configuration.

        Parses the instance name to extract GitHub repository information and
        sets up the instance with the provided method, model, and trajectory path.
        The instance name must follow the format "owner__repo__pr_number".

        Args:
            instance_name: Full instance identifier in format "owner__repo__pr_number"
                         (e.g., "microsoft__vscode__12345")
            instance_method: Method or approach used for this instance
                           (e.g., "swe-agent", "moatless", "autocoderover")
            instance_model: Name of the LLM model used for processing
                          (e.g., "claude-3.5-sonnet", "gpt-4", "deepseek-coder")
            instance_traj_path: Filesystem path to the trajectory data files
                              for this instance

        Raises:
            ValueError: If instance_name doesn't contain exactly 3 parts when
                       split by "__" (owner, repo, pr_number)
        """
        self.name = instance_name
        # Parse instance name into owner, repo and PR number components
        self.owner, self.repo, self.pr_number = instance_name.split("__")
        # Create formatted ID for dataset lookups (uses dash instead of double underscore)
        self.id = f"{self.owner}__{self.repo}-{self.pr_number}"
        # Generate direct GitHub pull request URL
        self.pr_link = f"https://github.com/{self.owner}/{self.repo}/pull/{self.pr_number}"
        self.method = instance_method
        self.model = instance_model
        # Store path to trajectory data files for later loading
        self.traj_path = instance_traj_path

    def __str__(
        self,
    ) -> str:
        """
        Return a human-readable string representation of the instance.

        Provides a concise summary of the instance including its name and
        the model used for processing. Useful for debugging, logging, and
        displaying instance information.

        Returns:
            A formatted string showing the instance name and model information
        """
        return f"MultiSWEInstance(name={self.name}, model={self.model})"

    @property
    def full_trajs(
        self,
    ) -> List:
        """
        Get the complete trajectory data for this instance.

        This is an abstract property that must be implemented by subclasses
        to provide access to the full trajectory data. Subclasses typically
        implement lazy loading to load trajectory data from files when first accessed.

        Returns:
            List of trajectory data objects. The exact structure depends on
            the specific SWE agent implementation.

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Note:
            Subclasses should implement caching mechanisms to avoid reloading
            data on subsequent accesses.
        """
        raise NotImplementedError("Subclass must implement this method")

    @property
    def example_trajs(
        self,
    ) -> List:
        """
        Get example trajectory data for this instance.

        This is an abstract property that must be implemented by subclasses
        to provide access to example or demonstration trajectory data. This
        might include reference solutions or example interactions.

        Returns:
            List of example trajectory data objects. The exact structure
            depends on the specific SWE agent implementation.

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Note:
            Example trajectories are typically used for few-shot learning
            or providing reference solutions for evaluation.
        """
        raise NotImplementedError("Subclass must implement this method")

    @property
    def llm_trajs(
        self,
    ) -> List:
        """
        Get LLM-specific trajectory data for this instance.

        This is an abstract property that must be implemented by subclasses
        to provide access to LLM interaction trajectories. This typically
        includes the conversation history, prompts, and responses between
        the agent and the language model.

        Returns:
            List of LLM trajectory data objects containing conversation
            history and model interactions.

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Note:
            LLM trajectories are crucial for analyzing model behavior,
            debugging agent decisions, and improving prompt engineering.
        """
        raise NotImplementedError("Subclass must implement this method")

    @property
    def version(
        self,
    ) -> str:
        """
        Get the dataset version for this instance with lazy loading.

        Retrieves the version information from the rustbench dataset on Hugging Face.
        The version is loaded lazily - it's only fetched from the dataset the first
        time this property is accessed, then cached for subsequent access.

        Returns:
            Version string from the dataset, with whitespace stripped

        Raises:
            Exception: If the instance is not found in the dataset or if there
                      are issues accessing the Hugging Face dataset

        Note:
            This method requires internet connectivity to access the Hugging Face
            dataset. The version information is cached after the first successful load.
        """
        if not hasattr(self, "_version"):
            self._version = None  # Initialize cache
            try:
                # Load dataset and filter by instance ID to find this specific instance
                dataset = load_dataset(MULTISWE_DATASET_NAME, split="train")
                filtered = dataset.filter(lambda x: x["instance_id"] == self.id)
                # Extract and clean the version string
                self._version = filtered[0]["version"].strip()
            except:
                # Re-raise any exception (network issues, dataset not found, etc.)
                raise
        return self._version

    def get_llm_call_request_trajs(
        self,
    ) -> List[dict]:
        """
        Get trajectories of LLM call requests for this instance.

        This is an abstract method that must be implemented by subclasses to
        provide access to the request trajectories sent to the language model.
        These typically include prompts, system messages, and user inputs.

        Returns:
            List of dictionaries containing LLM request trajectory data.
            Each dictionary represents one request sent to the language model.

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Note:
            Request trajectories are useful for analyzing prompt patterns,
            debugging model inputs, and understanding agent behavior.
        """
        raise NotImplementedError("Subclass must implement this method")

    def get_llm_call_response_trajs(
        self,
    ) -> List[dict]:
        """
        Get trajectories of LLM call responses for this instance.

        This is an abstract method that must be implemented by subclasses to
        provide access to the response trajectories received from the language model.
        These typically include model outputs, generated code, and reasoning.

        Returns:
            List of dictionaries containing LLM response trajectory data.
            Each dictionary represents one response received from the language model.

        Raises:
            NotImplementedError: This method must be implemented by subclasses

        Note:
            Response trajectories are essential for evaluating model performance,
            analyzing generated solutions, and understanding model reasoning patterns.
        """
        raise NotImplementedError("Subclass must implement this method")
