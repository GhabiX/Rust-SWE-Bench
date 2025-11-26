"""
Base Docker utilities for container management and operations.

This module provides a high-level abstraction layer over the Docker API,
offering simplified interfaces for common Docker operations including:

- Docker client connection management with automatic error handling
- Image operations (pull, check existence, remove)
- Container lifecycle management (run, stop, status checking)
- File operations within containers
- Context manager support for automatic cleanup

The module is designed to handle Docker API errors gracefully and provide
consistent error reporting through custom DockerError exceptions. It includes
retry mechanisms for unreliable operations like image pulling and container
status monitoring.

Classes:
    DockerError: Custom exception for Docker-related operations
    DockerClient: High-level Docker client wrapper with connection management
    DockerContainer: Container lifecycle manager with context manager support
"""

import io
import logging
import os
import secrets  # For generating random suffixes in container names
import tarfile
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import docker
import docker.errors
import docker.models.containers

from replay.utils.decorator import func_retry
from replay.utils.error import error_single_line_message
from replay.utils.log import log_info
from replay.utils.uuid import uuid_str


class DockerError(Exception):
    """
    Custom exception class for Docker-related operations and API errors.
    
    This exception is raised when Docker operations fail, providing a consistent
    error handling mechanism across all Docker-related functions. It wraps
    underlying Docker API errors and provides simplified error messages.
    """

    pass


class DockerClient:
    """
    High-level Docker client wrapper providing simplified Docker operations.
    
    This class wraps the Docker API client and provides a simplified interface
    for common Docker operations. It handles connection management, error handling,
    and provides retry mechanisms for unreliable operations.
    
    Features:
    - Automatic Docker daemon connection with health checking
    - Image management (pull, check existence, remove)
    - Container operations (run, check existence)
    - Integrated error handling with custom exceptions
    - Retry mechanisms for network-dependent operations
    """

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize Docker client and establish connection to Docker daemon.

        Creates a Docker client from environment variables and tests the connection
        by pinging the Docker daemon. This ensures that Docker is available and
        accessible before performing any operations.

        Args:
            logger: Optional logger instance for operation logging. If None,
                   logging operations will be skipped.

        Raises:
            DockerError: When Docker daemon connection fails, typically due to:
                        - Docker daemon not running
                        - Permission issues (user not in docker group)
                        - Network connectivity problems
                        - Invalid Docker configuration
        """
        self.logger = logger
        try:
            # Create Docker client from environment (DOCKER_HOST, etc.)
            self.client = docker.from_env()
            # Test connection to ensure Docker daemon is accessible
            self.client.ping()
        except Exception as e:
            raise DockerError(f"Docker connection failed -- {error_single_line_message(e)}")

    def image_exists(self, image_name: str) -> bool:
        """
        Check if a Docker image exists in the local Docker registry.

        This method queries the local Docker image registry to determine if
        the specified image is available locally. It's useful for checking
        image availability before attempting to run containers.

        Args:
            image_name: Full name of the Docker image to check, including
                       tag if needed (e.g., "ubuntu:20.04", "my-app:latest")

        Returns:
            bool: True if the image exists locally, False otherwise

        Raises:
            DockerError: When the image check operation fails due to API errors
                        (excluding normal "image not found" cases)
        """
        try:
            # Attempt to retrieve image information
            self.client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            # Image doesn't exist - this is expected behavior, not an error
            return False
        except Exception as e:
            # Unexpected error during image check
            raise DockerError(f"Image check failed -- {error_single_line_message(e)}")

    def image_remove(self, image_name: str):
        """
        Remove a Docker image from the local registry.

        This method forcefully removes the specified image from the local Docker
        registry. It will not raise an error if the image doesn't exist, making
        it safe to call for cleanup operations.

        Args:
            image_name: Full name of the Docker image to remove, including
                       tag if needed (e.g., "ubuntu:20.04", "my-app:latest")

        Raises:
            DockerError: When image removal fails due to API errors
                        (excluding normal "image not found" cases)

        Note:
            Uses force=True to remove images even if they have dependent containers
            or intermediate layers. This ensures cleanup operations succeed.
        """
        try:
            # Force removal of the image and all its layers
            self.client.images.remove(image_name, force=True)
        except docker.errors.ImageNotFound:
            # Image doesn't exist - this is fine, no action needed
            pass
        except Exception as e:
            raise DockerError(f"Image remove failed -- {error_single_line_message(e)}")

    @func_retry(max_attempts=30, delay=60)
    def image_pull(self, image_name: str):
        """
        Pull a Docker image from a registry with automatic retry.

        Downloads the specified Docker image from a registry (Docker Hub by default).
        This operation includes automatic retry logic to handle temporary network
        issues or registry unavailability.

        Args:
            image_name: Full name of the Docker image to pull, including
                       tag if needed (e.g., "ubuntu:20.04", "my-app:latest")

        Raises:
            DockerError: When image pull fails after all retry attempts,
                        typically due to:
                        - Image not found in registry
                        - Authentication issues
                        - Network connectivity problems
                        - Insufficient disk space

        Note:
            Uses retry decorator with 30 attempts and 60-second delays between
            retries, providing up to 30 minutes of retry time for large images
            or slow network conditions.
        """
        try:
            log_info(self.logger, f"📥 Pulling image: {image_name}")
            # Pull the image from the registry
            self.client.images.pull(image_name)
            log_info(self.logger, f"✅ Image pull successful: {image_name}")
        except Exception as e:
            raise DockerError(f"Image pull failed -- {error_single_line_message(e)}")

    def container_exists(self, container_name: str) -> bool:
        """
        Check if a Docker container exists (running or stopped).

        This method queries Docker to determine if a container with the specified
        name exists, regardless of its current state (running, stopped, etc.).

        Args:
            container_name: Name of the container to check

        Returns:
            bool: True if the container exists, False otherwise

        Raises:
            DockerError: When the container search operation fails due to API errors
                        (excluding normal "container not found" cases)
        """
        try:
            # Attempt to retrieve container information
            self.client.containers.get(container_name)
            return True
        except docker.errors.NotFound:
            # Container doesn't exist - this is expected behavior, not an error
            return False
        except Exception as e:
            # Unexpected error during container search
            raise DockerError(f"Container search failed -- {error_single_line_message(e)}")

    def container_run(
        self,
        image_name: str,
        container_name: Optional[str] = None,
        auto_image_pull: bool = True,
        **kwargs: Any,
    ) -> docker.models.containers.Container:
        """
        Create and start a new Docker container.

        This method handles the complete container creation process, including
        name conflict checking, image availability verification, and automatic
        image pulling if needed.

        Args:
            image_name: Name of the Docker image to use for the container
            container_name: Optional name for the container. If None, Docker
                          will assign a random name.
            auto_image_pull: If True, automatically pull the image if it doesn't
                           exist locally. If False, raise an error for missing images.
            **kwargs: Additional keyword arguments passed directly to the Docker
                     containers.run() method (e.g., ports, volumes, environment)

        Returns:
            docker.models.containers.Container: The created and started container object

        Raises:
            DockerError: When container creation fails due to:
                        - Container name conflicts (container already exists)
                        - Image not found (when auto_image_pull=False)
                        - Docker API errors during container creation
                        - Resource constraints (insufficient memory, etc.)
        """
        try:
            # Check for container name conflicts
            if container_name and self.container_exists(container_name):
                raise DockerError(f"Container {container_name} already exists")

            # Ensure the required image is available locally
            if not self.image_exists(image_name):
                if auto_image_pull:
                    # Automatically pull the missing image
                    self.image_pull(image_name)
                else:
                    # Fail if auto-pull is disabled
                    raise DockerError(f"Image {image_name} does not exist")

            # Create and start the container
            return self.client.containers.run(
                image=image_name,
                name=container_name,
                **kwargs,
            )

        except docker.errors.APIError as e:
            # Docker API specific errors
            raise DockerError(f"Container run failed -- {error_single_line_message(e)}")
        except Exception as e:
            # Any other unexpected errors
            raise DockerError(f"Container unknown error -- {error_single_line_message(e)}")


class DockerContainer:
    """
    High-level Docker container lifecycle manager with context manager support.
    
    This class provides a comprehensive interface for managing Docker container
    lifecycles, from creation to cleanup. It supports both programmatic control
    and automatic resource management through Python's context manager protocol.
    
    Key Features:
    - Automatic container naming and configuration management
    - Context manager support for automatic cleanup
    - Container status monitoring with retry mechanisms
    - File operations within containers
    - Comprehensive logging and error handling
    - Default configuration optimized for development and testing
    
    The class handles common Docker operations like starting, stopping, and
    monitoring containers, while providing sensible defaults for most use cases.
    """

    def __init__(
        self,
        image_name: str,
        client: Optional[DockerClient] = None,
        container_name: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ):
        """
        Initialize Docker container manager with configuration.

        Sets up the container manager with the specified image and configuration.
        The container is not started until explicitly requested via run() or
        when entering a context manager.

        Args:
            image_name: Name of the Docker image to use for the container
            client: Optional DockerClient instance. If None, a new client will be created.
            container_name: Optional name for the container. If None, a unique name
                          will be automatically generated using timestamp and random data.
            logger: Optional logger instance for operation logging
            **kwargs: Additional keyword arguments that override default container
                     configuration. These are passed to docker.containers.run()

        Default Container Configuration:
            - network_mode: "host" (use host networking)
            - auto_remove: True (automatically remove when stopped)
            - stdin_open: True (keep STDIN open)
            - tty: True (allocate a pseudo-TTY)
            - detach: True (run in background)
        """
        self.logger = logger
        self.client = client or DockerClient(logger)
        self.image_name = image_name
        self.container_name = container_name or self._default_container_name()
        self.container = None  # Will hold the container object when running
        
        # Set sensible defaults for container configuration
        self.kwargs: Dict[str, Any] = {
            "network_mode": "host",     # Use host networking for simplicity
            "auto_remove": True,        # Clean up automatically when stopped
            "stdin_open": True,         # Keep STDIN open for interactive use
            "tty": True,               # Allocate pseudo-TTY for proper terminal support
            "detach": True,            # Run in background (non-blocking)
        }
        # Allow user-provided kwargs to override defaults
        self.kwargs.update(kwargs)

    def _default_container_name(self) -> str:
        """
        Generate a unique default container name based on current timestamp.

        Creates a container name using the format "container-{timestamp}-{random_suffix}"
        to ensure uniqueness and avoid naming conflicts.

        Returns:
            A unique container name string
        """
        timestamp = str(int(time.time()))
        random_suffix = uuid_str()  # 6 character hex string
        return f"container-{timestamp}-{random_suffix}"

    @func_retry(max_attempts=180, delay=1.0)
    def _wait_running(
        self,
    ):
        """
        Wait for container to enter running state with retry logic.

        This method continuously checks the container status until it reaches
        the "running" state or the maximum retry attempts are exceeded. Uses
        the retry decorator to handle transient Docker API issues.

        The method will retry for up to 180 attempts with 1-second delays,
        providing up to 3 minutes for the container to start properly.

        Raises:
            DockerError: If container fails to reach running state within
                        the timeout period or encounters startup errors

        Note:
            This is an internal method called automatically by run().
            The retry behavior helps handle slow-starting containers
            or temporary Docker API unavailability.
        """
        if not self.is_running():
            raise DockerError(f"Container {self.container_name} failed to run")

    def run(self) -> None:
        """
        Start the Docker container and wait for it to become ready.

        This method initiates the container using the configured image and settings,
        then waits for the container to reach the running state. It provides detailed
        logging of the startup process including container metadata.

        The method will automatically pull the image if it doesn't exist locally
        (when auto_image_pull was set to True during client creation).

        Raises:
            DockerError: When container startup fails due to:
                        - Image not found (if auto_image_pull=False)
                        - Container name conflicts
                        - Resource constraints (memory, CPU, etc.)
                        - Docker API errors
                        - Container fails to start within timeout period

        Side Effects:
            - Sets self.container to the running container object
            - Logs startup progress and container details
            - Container becomes available for operations
        """
        log_info(self.logger, f"🚀 Starting container...")
        self.container = self.client.container_run(
            image_name=self.image_name,
            container_name=self.container_name,
            auto_image_pull=False,
            **self.kwargs,
        )
        self._wait_running()  # Wait for container to be fully ready
        log_info(self.logger, f"✅ Container started successfully:")
        log_info(self.logger, f"\tContainer name: {self.container_name}")
        log_info(self.logger, f"\tImage name: {self.image_name}")
        log_info(self.logger, f"\tContainer ID: {self.container.id}")

    def stop(self) -> None:
        """
        Stop the container

        Attempts to gracefully stop the container. If it fails and the container is configured
        for auto-removal, it forcefully removes the container. This dual mechanism ensures
        container resources are always correctly released, avoiding resource leaks.

        Process:
        1. Try to gracefully stop the container, waiting up to 1800 seconds
        2. If stopping fails and container is configured for auto-removal, forcefully remove it
        3. Clean up container reference and log the operation

        Raises:
            DockerError: When both container stop and removal fail
        """
        try:
            log_info(self.logger, f"🛑 Stopping container: {self.container_name}")
            try:
                self.container.stop(timeout=1800)
            except:
                if "auto_remove" in self.kwargs and self.kwargs["auto_remove"]:
                    self.container.remove(force=True)
            self.container = None
            log_info(self.logger, f"✅ Container stopped successfully: {self.container_name}")
        except Exception as e:
            raise DockerError(f"Container stop failed -- {error_single_line_message(e)}")

    def __enter__(self) -> "DockerContainer":
        """
        Support context manager pattern, start container when entering

        Returns:
            DockerContainer: Current instance
        """
        # Ensure container is running
        self.run()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Automatically clean up container when leaving context

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback information
        """
        self.stop()

    def status(self) -> str:
        """
        Get container status

        Returns:
            str: Container status string

        Raises:
            DockerError: When container is not running
        """
        if not self.container:
            raise DockerError("Container not running")
        self.container.reload()
        return self.container.status

    def is_running(self) -> bool:
        """
        Check if container is running

        Returns:
            bool: Whether container is running
        """
        return self.container and self.status() == "running"

    def exists(self) -> bool:
        """
        Check if container exists

        Returns:
            bool: Whether container exists
        """
        return self.container and self.client.container_exists(self.container_name)

    def logs(self, **kwargs: Any) -> str:
        """
        Get container logs

        Args:
            kwargs: Parameters passed to container.logs

        Returns:
            str: Container logs content

        Raises:
            DockerError: When container is not running
        """
        if not self.container:
            raise DockerError("Container not running")
        return self.container.logs(**kwargs).decode("utf-8", errors="replace")

    def write_file(
        self,
        dst_path_in_container: str,
        content: Union[str, bytes],
    ) -> None:
        """
        Write content to a file in the container

        Args:
            file_path: Path to the file
            content: Content to write to the file
        """
        # convert content to bytes
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            raise DockerError(f"Invalid content type: {type(content)}")

        dst_dir_in_container = os.path.dirname(dst_path_in_container)
        dst_file_in_container = os.path.basename(dst_path_in_container)

        log_info(self.logger, f"📦 Writing {len(content_bytes)} bytes to '{self.container_name}:{dst_path_in_container}'")

        try:
            # Create an in-memory tar archive
            pw_tarstream = io.BytesIO()
            with tarfile.open(fileobj=pw_tarstream, mode="w") as tar:
                tarinfo = tarfile.TarInfo(name=dst_file_in_container)
                tarinfo.size = len(content_bytes)
                tarinfo.mtime = int(time.time())
                # Add the file info and then the file content
                tar.addfile(tarinfo, io.BytesIO(content_bytes))

            # Rewind the stream to the beginning and send it to the container
            pw_tarstream.seek(0)
            self.container.put_archive(path=dst_dir_in_container, data=pw_tarstream)

            log_info(self.logger, f"✅ Successfully wrote file to '{self.container_name}:{dst_path_in_container}'")

        except docker.errors.APIError as e:
            raise DockerError(f"Failed to write file to container -- {error_single_line_message(e)}")
        except Exception as e:
            raise DockerError(f"An unexpected error occurred while writing file -- {error_single_line_message(e)}")
