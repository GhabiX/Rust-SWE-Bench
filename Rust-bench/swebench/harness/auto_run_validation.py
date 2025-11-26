import os
import subprocess
import logging
import argparse
import re


#TODO:path
ROOT_PATH = "Rust-bench/swebench"
TASK_NAME = "auto"


input_folder = os.path.join(ROOT_PATH, f"collect/tasks/{TASK_NAME}")
output_folder = os.path.join(ROOT_PATH, f"versioning/auto__{TASK_NAME}__results")
version_folder = os.path.join(ROOT_PATH, f"versioning/auto__{TASK_NAME}/version")
env_commit_folder = os.path.join(ROOT_PATH, f"versioning/auto__{TASK_NAME}/env_commit")
versioning_log_folder = os.path.join(ROOT_PATH, f"versioning/auto__{TASK_NAME}/log")
dataset_folder = os.path.join(ROOT_PATH, f"versioning/auto__{TASK_NAME}/dataset")

if not os.path.exists(input_folder):
    raise RuntimeError("Input Folder Not Exists")
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
if not os.path.exists(version_folder):
    os.makedirs(version_folder)
if not os.path.exists(env_commit_folder):
    os.makedirs(env_commit_folder)
if not os.path.exists(versioning_log_folder):
    os.makedirs(versioning_log_folder)
if not os.path.exists(dataset_folder):
    os.makedirs(dataset_folder)

num_workers = 6  


def setup_logging(rerun):

    log_mode = "w" if rerun else "a"  
    log_file = os.path.join(versioning_log_folder, 'process.log')
    log_file_detail = os.path.join(versioning_log_folder, 'process_detail.log')

    
    if rerun and os.path.exists(log_file_detail):
        open(log_file_detail, 'w').close()  
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode=log_mode),
            logging.StreamHandler()  
        ]
    )
    return log_file, log_file_detail


def run_command_with_logging(command, description, log_file_detail):

    logging.info(f"Running: {description} -> {' '.join(command)}")
    with open(log_file_detail, 'a') as log:  
        try:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=log,
                text=True,
                check=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running {description}: {e}")
            return None


def main(args):
    print(args.rerun)
    log_file, log_file_detail = setup_logging(args.rerun)
    finish = []
    if not args.rerun:  
        processing_pattern = re.compile(r"Processing: (\S+)")
        with open(log_file, 'r', encoding='utf-8') as log:
            for line in log:
                
                processing_match = processing_pattern.search(line)
                if processing_match:
                    task = processing_match.group(1)
                    finish.append(task)
    # print(f"finish:{finish}")
    
    for root, dirs, files in os.walk(input_folder):
        for file in sorted(files, reverse=args.reverse):
            # print(f"file :{file}")
            if file.endswith(".jsonl") and file not in finish:
                logging.info(f"Processing: {file}")
                instances_path = os.path.join(root, file)
                base_name = os.path.splitext(file)[0]
                base_name = base_name.split(".")[0]
                version_path = version_folder + f"/{base_name}_versions.json"

                # Step 1: 运行 get_versions.py
                if not os.path.exists(version_path):
                    get_versions_command = [
                        "python", f"{ROOT_PATH}/versioning/get_versions.py",
                        "--instances_path", instances_path,
                        "--retrieval_method", "github",
                        "--num_workers", str(num_workers),
                        "--output_dir", version_folder,
                        "--cleanup"
                    ]
                    result =  run_command_with_logging(get_versions_command, f"get_versions {file}", log_file_detail)
                    if result is None:
                        continue

                # Step 2: 运行 environment_setup_commit.py
                if not os.path.exists(f"{ROOT_PATH}/versioning/auto/dataset/{base_name}_versions.json"):
                    environment_setup_command = [
                        "python", f"{ROOT_PATH}/versioning/environment_setup_commit.py",
                        "--dataset_name", version_path,
                        "--output_dir", dataset_folder
                    ]
                    result = run_command_with_logging(environment_setup_command, f"environment_setup_commit {file}", log_file_detail)
                    if result is None:
                        os.remove(version_path)
                        continue
                
                # Step 3: 运行 run_validation.py
                run_validation_command = [
                    "python", f"{ROOT_PATH}/harness/run_validation.py",
                    "--dataset_name", f"{dataset_folder}/{base_name}_versions.json",
                    "--run_id", f"{base_name}_versions",
                    "--max_workers", str(num_workers),
                    "--cache_level", "base",
                    "--auto", "True",
                    "--clean","True",
                    "--output_dir", output_folder,
                ]
                run_command_with_logging(run_validation_command, f"run_validation {file}", log_file_detail)
        logging.info(f"Finished: {file}")
    logging.info("All tasks completed.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rerun', action='store_true', help="设置为 True 表示覆盖日志文件重新运行")
    parser.add_argument('--reverse', action='store_true', help="设置为 True 表示运行文件的顺序将从字典序的反向运行")
    args = parser.parse_args()
    main(args)
