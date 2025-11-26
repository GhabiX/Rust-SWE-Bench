import sys
import json
import docker
import random
from docker.errors import ImageNotFound, APIError, DockerException
from typing import List, Dict, Optional, Union, Any
import concurrent.futures
import os


SETUP_CMD = """
echo "Starting setup script..."
mkdir -p /workspace
echo "Created /workspace directory."

cp -r /home/{instance_repo} /workspace/{instance_workspace_name}


echo "Setting up environment..."
echo "Installing Python 3.11..."
apt-get update
apt-get install -y software-properties-common
add-apt-repository ppa:deadsnakes/ppa -y
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev pip
echo "Python 3.11 installed successfully."

python3.11 -m venv /workspace/rta-venv
source /workspace/rta-venv/bin/activate
pip install langchain langchain-openai openai langchain_community loguru
export TZ=Asia/Hong_Kong
export RUSTFLAGS="-A warnings"
echo "Setup script completed."

export USER=root

mkdir -p /home/rust_tracer/
export CARGO_TARGET_DIR=/home/rust_target/
echo "Set CARGO_TARGET_DIR to /home/rust_tracer/ for isolated compilation"
rustup toolchain uninstall stable && rustup toolchain install stable
rustup default stable
cd /RTAgent/rustforger-tracer && cargo build --release && cargo install --path trace_cli
cd /workspace

echo "Starting RTA..."
python3 /RTAgent/src/rustforger_main_tracing.py --model {model_name} --instance {instance_id}
echo "Resolved completed."
"""

ContainerObject = docker.models.containers.Container

def run_command_in_container(
    client: docker.DockerClient,
    image_name: str,
    command: Optional[Union[str, List[str]]] = None, # Optional: uses image's default CMD if None
    container_name: Optional[str] = None,
    privileged: bool = False,
    network_mode: Optional[str] = None,
    volumes: Optional[Dict[str, Dict[str, str]]] = None,
    environment: Optional[Dict[str, str]] = None,
    ports: Optional[Dict[str, Optional[Union[int, str, List[Union[int, str]]]]]] = None,
    stdin_open: bool = False,
    tty: bool = False,
    remove: bool = True,
    detach: bool = False,
    pull_image_if_not_found: bool = True,
    mem_limit: Optional[str] = None  # Memory limit (e.g., '32g', '1024m')
) -> Union[bytes, ContainerObject, None]:
    """
    Pulls an image (if specified and not found), then creates and runs a container
    with the specified command and parameters.

    This function focuses on running a command in a new container from an image,
    similar to 'docker run'. If "build container" implies building an image from a
    Dockerfile, you would use client.images.build() separately before calling this function.

    Args:
        client: Initialized DockerClient instance.
        image_name: Name of the Docker image (e.g., 'ubuntu:latest').
        command: Command to run inside the container (string or list of strings).
                 If None, the image's default command (CMD) is used. (Default: None)
        container_name: Optional name for the container. If None, Docker generates a name. (Default: None)
        privileged: Run container in privileged mode. (Default: False)
        network_mode: Docker network mode (e.g., 'host', 'bridge'). (Default: None, uses Docker default)
        volumes: Volume mappings. Keys are host paths, values are dicts {'bind': container_path, 'mode': 'rw'/'ro'}.
                 Example: {'/host/path': {'bind': '/container/path', 'mode': 'rw'}} (Default: None)
        environment: Dictionary of environment variables to set in the container. Example: {'VAR1': 'value1'} (Default: None)
        ports: Port mappings. Example: {'2222/tcp': 3333} (container port: host port) (Default: None)
        stdin_open: Keep STDIN open even if not attached (corresponds to -i). (Default: False)
        tty: Allocate a pseudo-TTY (corresponds to -t). (Default: False)
        remove: Automatically remove the container when it exits. (Default: True)
        detach: Run container in the background. If True, returns a Container object.
                If False, waits for command to complete and returns logs. (Default: False)
        pull_image_if_not_found: If True, tries to pull the image if not found locally. (Default: True)
        mem_limit: Memory limit for the container (e.g., '32g', '1024m'). (Default: None)

    Returns:
        - If detach is False: The combined stdout and stderr logs from the container as bytes.
        - If detach is True: The docker.models.containers.Container object.
        - None if a critical error occurs (e.g., image pull fails and not ignored, or API error).
    """
    try:
        if pull_image_if_not_found:
            try:
                client.images.get(image_name)
                print(f"Image '{image_name}' already exists locally.")
            except ImageNotFound:
                print(f"Image '{image_name}' not found locally. Pulling image...")
                client.images.pull(image_name)
                print(f"Image '{image_name}' pulled successfully.")

        run_kwargs: Dict[str, Any] = {
            'image': image_name,
            'command': command,
            'name': container_name,
            'privileged': privileged,
            'network_mode': network_mode,
            'volumes': volumes,
            'environment': environment,
            'ports': ports,
            'stdin_open': stdin_open,
            'tty': tty,
            'remove': remove,
            'detach': detach,
            'mem_limit': mem_limit
        }
        
        # Docker SDK handles None for optional parameters like name, network_mode, volumes etc.
        # by using defaults or omitting them, so no need to manually filter them out.

        if detach:
            print(f"Starting container from image '{image_name}' in detached mode...")
            container = client.containers.run(**run_kwargs)
            print(f"Container '{container.name if container_name else container.id}' started.")
            return container
        else:
            print(f"Running command in container from image '{image_name}' (foreground)...")
            # client.containers.run() blocks until the command completes when detach=False
            # It returns the container's output (stdout/stderr logs).
            logs = client.containers.run(**run_kwargs)
            print(f"Command finished in container (from image '{image_name}').")
            if remove:
                 print(f"Container was (or will be) removed as per 'remove=True'.")
            return logs

    except ImageNotFound:
        print(f"ERROR: Image '{image_name}' could not be found or pulled.")
        return None
    except APIError as e:
        print(f"Docker API Error: {e}")
        if container_name and "Conflict" in str(e) and f"name \"/{container_name}\" is already in use" in str(e):
            print(f"Hint: A container with name '{container_name}' may already exist.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def process_instance(instance_info, model_name):
    """Process a single instance Docker container run"""
    org_name = instance_info['repo'].split('/')[0].lower()
    repo_name = instance_info['repo'].split('/')[1].lower()
    pr_number = instance_info['pull_number']
    instance_image_name = f'rustbench/{org_name}__{repo_name}:pr-{pr_number}'
    instance_container_name = f"rta-{instance_info['instance_id']}"
    instance_workspace_name = f'{org_name}__{repo_name}__0.1'
    
    print(instance_workspace_name)
    print(instance_image_name)
    print(instance_container_name)  

    try:
        docker_client = docker.from_env(timeout=18000) 
        docker_client.ping() # Check connection
        print("Successfully connected to Docker daemon.")
    except DockerException as e:
        print(f"ERROR: Could not connect to Docker daemon. Is Docker running? Details: {e}")
        return

    # Parameters from your docker run command
    is_privileged = True
    network = 'host'

    base_dir = os.path.dirname(os.path.dirname(__file__))  

    volumes_map = {
        os.path.join(base_dir, 'log'): {'bind': '/RTAgent/log', 'mode': 'rw'},
        os.path.join(base_dir, 'data'): {'bind': '/RTAgent/data', 'mode': 'ro'},
        os.path.join(base_dir, 'src'): {'bind': '/RTAgent/src', 'mode': 'ro'},
        os.path.join(base_dir, 'rustforger-tracer'): {'bind': '/RTAgent/rustforger-tracer', 'mode': 'ro'},
    }

    setup_cmd = SETUP_CMD.format(
        instance_repo=repo_name, \
        instance_id=instance_info['instance_id'], \
        model_name=model_name, \
        instance_workspace_name=instance_workspace_name)

    container_command = ['/bin/bash', '-c', setup_cmd]

    print(f"\nAttempting to run container '{instance_container_name}' from image '{instance_image_name}'...")
    
    # Clean up potentially conflicting container name
    try:
        existing_container = docker_client.containers.get(instance_container_name)
        print(f"Found existing container named '{instance_container_name}'. Attempting to remove it...")
        existing_container.remove(force=True)
        print(f"Successfully removed existing container '{instance_container_name}'.")
    except docker.errors.NotFound:
        print(f"No existing container named '{instance_container_name}' found. Proceeding.")
    except APIError as e:
        print(f"API error while trying to remove existing container '{instance_container_name}': {e}. Proceeding with caution.")

    # Call the function to run the container and execute the scripted commands
    output_logs = run_command_in_container(
        client=docker_client,
        image_name=instance_image_name,
        command=container_command,
        container_name=instance_container_name,
        privileged=is_privileged,
        network_mode=network,
        volumes=volumes_map,
        stdin_open=True,
        tty=True,
        remove=True,
        detach=False,
        mem_limit='32g'  # Set 32GB memory limit for container
    )

    if output_logs is not None:
        print(f"\n--- Output from container '{instance_container_name}' ---")
        try:
            print(output_logs.decode('utf-8'))
        except UnicodeDecodeError:
            print("Could not decode output as UTF-8. Raw bytes:")
            print(output_logs)
        print(f"--- End of output from container '{instance_container_name}' ---")
    else:
        print(f"Failed to run container '{instance_container_name}' or it produced no logs.")

    print(f"\nInstance {instance_info['instance_id']} processing finished.")


def load_instances(jsonl_path, filter_id=None, skip_existing_logs=False):
    """Load instance information from JSONL file
    
    Args:
        jsonl_path: Path to the JSONL file
        filter_id: Optional list of instance IDs to filter by
        skip_existing_logs: If True, skip instances that already have log files
        
    Returns:
        If filter_id is provided, returns a list with matching instances
        If filter_id is None, returns all instances from the file
        If skip_existing_logs is True, excludes instances with existing log files
    """
    
    instances = []
    
    with open(jsonl_path, 'r') as f:
        for line in f:
            data = json.loads(line)
            
            # Skip if log file already exists
            if skip_existing_logs:
                log_filename = f"rustforger_log_{data['instance_id']}.json"
                log_path = f"/data/RustAgent/RTAgent/log/{log_filename}"
                if os.path.exists(log_path):
                    continue
            
            if filter_id:
                if data['instance_id'] in filter_id:
                    instances.append(data)
            else:
                instances.append(data)  # Collect all instances
    return instances

# --- Main execution logic ---
if __name__ == "__main__":
    # model_name = "claude-3-7-sonnet-20250219"
    # model_name = "gpt-4o-2024-11-20"
    model_name = "o4-mini-2025-04-16"
    # model_name = "Qwen3-32B"
    worker = 3

    # Load instance data
    
    instances = load_instances('./data/rustbench-all.jsonl', ['clap-rs__clap-2161'])
    # instances = load_instances('/data/RustAgent/RTAgent/data/rustbench-all.jsonl', ['tokio-rs__tokio-6618'])
    
    # random instance list
    random.shuffle(instances)


    print(f"Processing {len(instances)} instances with {worker} threads")
    
    # Use thread pool to process instances, max 8 threads running simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker) as executor:
        futures = {executor.submit(process_instance, instance, model_name): instance['instance_id'] 
                  for instance in instances}
        
        for future in concurrent.futures.as_completed(futures):
            instance_id = futures[future]
            try:
                future.result()  # Get processing result (exceptions will be raised here)
                print(f"Instance {instance_id} completed successfully")
            except Exception as e:
                print(f"Instance {instance_id} generated an exception: {e}")
    
    print("\nAll instances processing completed.")