from __future__ import annotations
import time

import docker
import json
import resource
import traceback
import sys
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm
import os
import json
from typing import Dict, List, Any, Callable, Set, Tuple
from swebench.harness.constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    INSTANCE_IMAGE_BUILD_DIR,
    KEY_INSTANCE_ID,
    # RUN_EVALUATION_LOG_DIR,
)
from swebench.harness.docker_utils import (
    remove_image,
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
    list_images,
    should_remove,
    clean_images,
)
from swebench.harness.docker_build import (
    BuildImageError,
    build_container,
    build_env_images,
    close_logger,
    setup_logger,
)
from typing import List, Dict, Callable
from swebench.harness.grading import get_eval_report
from swebench.harness.test_spec import make_nightly_test_spec, make_test_spec, TestSpec, make_test_spec_nightly_wo_feature,make_test_spec_wo_features
from swebench.harness.utils import load_swebench_dataset, str2bool
from swebench.harness.grading import get_logs_eval   
from swebench.harness.run_evaluation import get_gold_predictions, EvaluationError, get_dataset_from_preds

RUN_EVALUATION_LOG_DIR = Path("logs/run_validation")

def run_instance(
        test_spec: TestSpec,
        pred: dict,
        rm_image: bool,
        force_rebuild: bool,
        client: docker.DockerClient,
        run_id: str,
        timeout: int | None = None,
        auto: bool = False,
        config: str = "default",
    ):
    """
    Run a single instance with the given prediction.

    Args:
        test_spec (TestSpec): TestSpec instance
        pred (dict): Prediction w/ model_name_or_path, model_patch, instance_id
        rm_image (bool): Whether to remove the image after running
        force_rebuild (bool): Whether to force rebuild the image
        client (docker.DockerClient): Docker client
        run_id (str): Run ID
        timeout (int): Timeout for running tests

    Returns:

    """ 
    # Set up logging directory
    instance_id = test_spec.instance_id
    model_name_or_path = pred.get("model_name_or_path", "None").replace("/", "__")
    version_dir = f"{test_spec.repo.replace('/','_')}.{test_spec.version.replace('.','_')}"
    if auto:
        log_dir = RUN_EVALUATION_LOG_DIR / "auto" /run_id /config/ model_name_or_path / version_dir / instance_id
    else:
        log_dir = RUN_EVALUATION_LOG_DIR / run_id  /config/ model_name_or_path/ version_dir  / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Link the image build dir in the log dir
    build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__") / config
    image_build_link = log_dir / "image_build_dir"
    if not image_build_link.exists():
        try:
            # link the image build dir in the log dir
            image_build_link.symlink_to(build_dir.absolute(), target_is_directory=True)
        except:
            # some error, idk why
            pass
    log_file = log_dir / "run_instance.log"
    # Set up report file + logger
    report_path = log_dir / "report.json"
    if report_path.exists():
        return instance_id, json.loads(report_path.read_text())
    logger = setup_logger(instance_id, log_file)
    logger.info(f"build_dir: {build_dir} config: {config}")
    tests_changed = Path(log_dir / "tests_changed.txt")
    
    tests_changed.write_text("\n".join(test_spec.tests_changed))

    # Run the instance
    container = None
    try:
        # if test_spec.version is None:
        #     raise EvaluationError(
        #         instance_id,
        #         "No version found for instance",
        #         logger,
        #     )
        # Build + start instance container (instance image should already be built)
        container = build_container(test_spec, client, run_id, logger, rm_image, force_rebuild, build_dir)
        container.start()
        logger.info(f"Container for {instance_id} started: {container.id}")
        
        # Run eval script before patch, write output to logs
        eval_file = Path(log_dir / "eval.sh")
        eval_file.write_text(test_spec.eval_script)
        run_file = Path(log_dir / "run.sh")
        run_file.write_text(test_spec.pre_run_script)
        copy_to_container(container, eval_file, Path("/eval.sh"))
        copy_to_container(container, run_file, Path("/run.sh"))
        # log_file = Path(log_dir / "run.log")
        run_output, run_timed_out, run_total_runtime = exec_run_with_timeout(container, "/bin/bash /run.sh", timeout)
        run_output_path = log_dir/"run_output.txt"
        logger.info(f"Test runtime: {run_total_runtime:_.2f} seconds")
        with open(run_output_path, "w") as f:
            f.write(run_output)
            logger.info(f"Run output for {instance_id} written to {log_dir / 'run_output.txt'}")
            if run_timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    instance_id,
                    f"Run script timed out after {timeout} seconds.",
                    logger,
                )
        
        test_output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
        test_output_before_patch_path = log_dir / "test_output_before_patch.txt"
        logger.info(f'Test runtime: {total_runtime:_.2f} seconds')
        with open(test_output_before_patch_path, "w") as f:
            f.write(test_output)
            logger.info(f"Test output before patch for {instance_id} written to {test_output_before_patch_path}")
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )
        
        # Copy model prediction as patch file to container
        patch_file = Path(log_dir / "patch.diff")
        patch_file.write_text(pred["model_patch"] or "")
        logger.info(
            f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
        )
        copy_to_container(container, patch_file, Path("/tmp/patch.diff"))

        # Attempt to apply patch to container
        val = container.exec_run(
            "git apply -v /tmp/patch.diff",
            workdir="/testbed",
            user="root",
        )
        if val.exit_code != 0:
            logger.info(f"Failed to apply patch to container, trying again...")
            
            # try "patch --batch --fuzz=5 -p1 -i {patch_path}" to try again
            val = container.exec_run(
                "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff",
                workdir="/testbed",
                user="root",
            )
            if val.exit_code != 0:
                logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                raise EvaluationError(
                    instance_id,
                    f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
                    logger,
                )
            else:
                logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
        else:
            logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")

        # Get git diff before running eval script
        git_diff_output_before = (
            container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        )
        logger.info(f"Git diff before:\n{git_diff_output_before}")

        # Run eval script, write output to logs
        test_output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
        test_output_path = log_dir / "test_output.txt"
        logger.info(f'Test runtime: {total_runtime:_.2f} seconds')
        with open(test_output_path, "w") as f:
            f.write(test_output)
            logger.info(f"Test output for {instance_id} written to {test_output_path}")
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )
        
        # Get git diff after running eval script
        git_diff_output_after = (
            container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
        )

        # Check if git diff changed after running eval script, avoid test patch overlap the patch
        logger.info(f"Git diff after:\n{git_diff_output_after}")
        if git_diff_output_after != git_diff_output_before:
            logger.info(f"Git diff changed after running eval script")

        report_map = {
            "instance_id": test_spec.instance_id,
            "FAIL_TO_PASS": [],
            "PASS_TO_PASS": [],
            "FAIL_TO_FAIL": [],
            "PASS_TO_FAIL": [],
        }
        run_sm , found_run = get_logs_eval(log_file, run_output_path)
        eval_sm, found = get_logs_eval(log_file, test_output_path)
        eval_sm_ref, found_ref = get_logs_eval(log_file, test_output_before_patch_path)
        if not found_run:
            raise EvaluationError(
                instance_id,
                "No run logs found",
                logger,
            )
        if not found:
            raise EvaluationError(
                instance_id,
                "No evaluation logs found",
                logger,
            )
        if not found_ref:
            raise EvaluationError(
                instance_id,
                "No reference evaluation logs found",
                logger,
            )

        flag = False
        for test, status in eval_sm.items():
            if status == "PASSED":
                flag = True
            if status == "PASSED" and eval_sm_ref.get(test, None) == "FAILED":
                report_map["FAIL_TO_PASS"].append(test)
            elif status == "PASSED" and run_sm.get(test, None) == "PASSED" and eval_sm_ref.get(test, None) != "PASSED":
                report_map["FAIL_TO_PASS"].append(test)
            elif status == "PASSED" and eval_sm_ref.get(test, None) == "PASSED":
                report_map["PASS_TO_PASS"].append(test)
            elif status == "FAILED" and eval_sm_ref.get(test, None) == "FAILED":
                report_map["FAIL_TO_FAIL"].append(test)
            elif status == "FAILED" and eval_sm_ref.get(test, None) == "PASSED":
                report_map["PASS_TO_FAIL"].append(test)
        
        if flag == False: 
            return False, report_map
            

        return True, report_map
    except EvaluationError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except BuildImageError as e:
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        error_msg = (f"Error in evaluating model for {instance_id}: {e}\n"
                     f"{traceback.format_exc()}\n"
                     f"Check ({logger.log_file}) for more information.")
        logger.error(error_msg)
        print(e)
    finally:
        # Remove instance container + image, close logger
        cleanup_container(client, container, logger)
        if rm_image:
            remove_image(client, test_spec.instance_image_key, logger)
        close_logger(logger)

class RunConfig:
    """定义运行配置"""
    def __init__(self, name: str, spec_builder: Callable, desc: str):
        self.name = name  
        self.spec_builder = spec_builder  
        self.desc = desc  

def run_instance_batch(
    test_specs: List,
    predictions: Dict,
    client: docker.DockerClient,
    run_id: str,
    config: RunConfig,
    cache_level: str,
    clean: bool,
    force_rebuild: bool,
    max_workers: int,
    timeout: int,
    auto: bool,
    reusable_images: set
) -> tuple[Dict, List[str]]:
    """运行一批实例，返回结果和失败的实例 ID"""
    results = {}
    failed_ids = []

    print(f"Running {len(test_specs)} {config.name} instances...")
    with tqdm(total=len(test_specs), smoothing=0, desc=config.desc) as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    run_instance,
                    test_spec,
                    predictions[test_spec.instance_id],
                    should_remove(test_spec.instance_image_key, cache_level, clean, reusable_images),
                    force_rebuild,
                    client,
                    run_id,
                    timeout,
                    auto,
                    config.name,
                ): test_spec.instance_id
                for test_spec in test_specs
            }
            for future in as_completed(futures):
                pbar.update(1)
                instance_id = futures[future]
                try:
                    tuple_res = future.result()
                    if tuple_res is not None:
                        stable, res = tuple_res
                    # stable, res = future.result()
                        if stable is False:
                            failed_ids.append(instance_id)
                            print(f"{config.name.capitalize()} instance {instance_id} failed.")
                        if res:
                            del res['instance_id']
                            results[instance_id] = res
                    else:
                        failed_ids.append(instance_id)
                        print(f"{config.name.capitalize()} instance {instance_id} returned None.")
                except Exception as e:
                    print(f"Error in {config.name} instance {instance_id}: {e}")
                    failed_ids.append(instance_id)

    return results, failed_ids

def run_instances(
    predictions: Dict,
    instances: List,
    cache_level: str,
    clean: bool,
    force_rebuild: bool,
    max_workers: int,
    run_id: str,
    timeout: int,
    auto: bool
) -> Dict:
    """
    优化后的并行运行实例函数，支持动态配置重试。
    """
    client = docker.from_env()

    
    configs = [
        RunConfig("default", make_test_spec, "Running instances"),
        RunConfig("test", make_test_spec_wo_features, "Running test instances"),
        RunConfig("nightly", make_nightly_test_spec, "Running nightly instances"),
        RunConfig("nightly_wo_features", make_test_spec_nightly_wo_feature, "Running nightly instances without features"),
    ]

    
    remaining_instances = instances
    all_results = {}
    reusable_images = set()
    log = {}
    if auto:
        log_dir = RUN_EVALUATION_LOG_DIR / "auto" / run_id 
    else:
        log_dir = RUN_EVALUATION_LOG_DIR / run_id 
    log_dir_file = log_dir / "log.json"

    
    log_dir.mkdir(parents=True, exist_ok=True)

    
    if not force_rebuild:
        test_specs = [spec for spec in map(make_test_spec, instances) if spec]
        instance_image_ids = {x.instance_image_key for x in test_specs}
        existing_images = {tag for image in client.images.list(all=True) for tag in image.tags}
        reusable_images = instance_image_ids.intersection(existing_images)
        if reusable_images:
            print(f"Found {len(reusable_images)} existing instance images. Will reuse them.")

    
    for config in configs:
        if not remaining_instances:
            break

        
        test_specs = [spec for spec in map(config.spec_builder, remaining_instances) if spec]
        if not test_specs:
            continue

        
        results, failed_ids = run_instance_batch(
            test_specs, predictions, client, run_id, config,
            cache_level, clean, force_rebuild, max_workers, timeout, auto, reusable_images
        )
        all_results.update(results)

        
        test_ids = {spec.instance_id for spec in test_specs}
        successful_ids = list(test_ids - set(failed_ids))
        log[config.name] = successful_ids

        
        remaining_instances = [inst for inst in remaining_instances if inst['instance_id'] in failed_ids]

    
    log["all_failed"] = [inst['instance_id'] for inst in remaining_instances]
    
    
    with open(log_dir_file, "w") as f:
        json.dump(log, f, indent=4)
    
    print("All instances run.")
    return all_results

def main(
        dataset_name: str,
        split: str,
        instance_ids: list,
        max_workers: int,
        force_rebuild: bool,
        cache_level: str,
        clean: bool,
        open_file_limit: int,
        run_id: str,
        timeout: int,
        auto: bool,
        output_dir: str,
    ):
    """
    Run evaluation harness for the given dataset and predictions.
    """
    # set open file limit
    assert len(run_id) > 0, "Run ID must be provided"
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    # client timeout None
    client = docker.from_env(timeout=None)

    predictions = get_gold_predictions(dataset_name, split)
    
    predictions = {pred[KEY_INSTANCE_ID]: pred for pred in predictions}

    # get dataset from predictions, list of instances
    dataset = get_dataset_from_preds(dataset_name, split, instance_ids, predictions, run_id)
    for instance in dataset:
        instance['FAIL_TO_PASS'] = []
        instance['PASS_TO_PASS'] = []
        instance['FAIL_TO_FAIL'] = []
        instance['PASS_TO_FAIL'] = []
    existing_images = list_images(client)
    print(f"Running {len(dataset)} unevaluated instances...")
    if not dataset:
        print("No instances to run.")
    else:
        # build environment images + run instances
        build_env_images(client, dataset, force_rebuild, max_workers)
        results = run_instances(predictions, dataset, cache_level, clean, force_rebuild, max_workers, run_id, timeout, auto)

    for instance in dataset:
        instance_id = instance["instance_id"]
        # print("instance-----------------------------------------------------------------------")
        # print(instance.keys())
        if instance_id in results:
            # merge two dictionaries, crash on duplicate keys
            # assert not any(k in instance for k in results[instance_id]), f"Duplicate keys in {instance_id}"
            instance.update(results[instance_id])

    update_json_file(dataset_name,dataset,auto,output_dir)

    # clean images + make final report
    clean_images(client, existing_images, cache_level, clean)
    


def update_json_file(dataset_name, dataset, auto, output_dir):
    
    timestamp = time.strftime("%Y-%m-%d", time.localtime())
    result_path = os.path.join(output_dir, f"auto_{timestamp}")
    os.makedirs(result_path, exist_ok=True)
    if auto :
        dataset_name_w_results_all =  os.path.join(result_path, "defaultconfig_validated_all.json")
        dataset_name_w_results = os.path.join(result_path, "defaultconfig_validated.json")
    else:
        if dataset_name.endswith(".json") or dataset_name.endswith(".jsonl"):
            dataset_name = dataset_name.split("/")[-1]
            last_dot_idx = dataset_name.rfind(".")
            dataset_name_w_results_all = "./results/"+ dataset_name[:last_dot_idx] + "_validated.all" + dataset_name[last_dot_idx:]
            dataset_name_w_results ="./results/"+ dataset_name[:last_dot_idx] + "_validated" + dataset_name[last_dot_idx:]
        else:
            last_dot_idx = dataset_name.rfind("/")
            dataset_name_w_results_all = "./results/" + dataset_name[last_dot_idx+1:] + "_validated.all" + ".json"
            dataset_name_w_results = "./results/" + dataset_name[last_dot_idx+1:] + "_validated" + ".json"
    # Helper function to update a file with new data
    def update_file(file_path, dataset):
        # Load existing data if file exists
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                existing_data = json.load(f)
        else:
            existing_data = []

        # Create a dictionary index by instance_id for quick lookup
        instance_dict = {item["instance_id"]: item for item in existing_data}

        # Update or add new instances
        for instance in dataset:
            instance_id = instance.get("instance_id")
            if instance_id:
                instance_dict[instance_id] = instance  # Update or add new instance
            else:
                print("Warning: Missing 'instance_id' in instance:", instance)

        # Write updated data back to file
        with open(file_path, "w") as f:
            json.dump(list(instance_dict.values()), f, indent=4)

    # Update both validated and validated.all files
    update_file(dataset_name_w_results_all, dataset)

    # Only include instances with FAIL_TO_PASS for validated file
    update_file(dataset_name_w_results, [inst for inst in dataset if len(inst.get("FAIL_TO_PASS", [])) > 0])

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset_name", default="princeton-nlp/SWE-bench_Lite", type=str, help="Name of dataset or path to JSON file.")
    parser.add_argument("--split", type=str, default="train", help="Split of the dataset")
    parser.add_argument("--instance_ids", nargs="+", type=str, help="Instance IDs to run (space separated)")
    parser.add_argument("--max_workers", type=int, default=4, help="Maximum number of workers (should be <= 75%% of CPU cores)")
    parser.add_argument("--open_file_limit", type=int, default=4096, help="Open file limit")
    parser.add_argument(
        "--timeout", type=int, default=3600, help="Timeout (in seconds) for running tests for each instance"
        )
    parser.add_argument(
        "--force_rebuild", type=str2bool, default=False, help="Force rebuild of all images"
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        help="Cache level - remove images above this level",
        default="env",
    )
    # if clean is true then we remove all images that are above the cache level
    # if clean is false, we only remove images above the cache level if they don't already exist
    parser.add_argument(
        "--clean", type=str2bool, default=False, help="Clean images above cache level"
    )
    parser.add_argument("--auto", type=str2bool, default=False, help="Run in auto mode")
    parser.add_argument("--run_id", type=str, required=True, help="Run ID - identifies the run")
    parser.add_argument("--output_dir", type=str, default=".", help="Output directory for logs")
    args = parser.parse_args()
    main(**vars(args))
