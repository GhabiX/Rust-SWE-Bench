# Quick Start

## Benchmark Setup

This section guides you through setting up the necessary environment and running the evaluation harness on the `Rust-bench` dataset.

## Installation

First, clone the repository and install the required dependencies:

```
# Navigate into the project directory
cd Rust-bench

# Install the package in editable mode
pip install -e .
```

Second, to build the instance images, use the commands below:

```
cd Rust-bench/swebench/harness
  
python run_evaluation.py \
    --dataset_name user2f86/rustbench\
    --run_id rustbench \
    --max_workers 10\
    --cache_level instance \
    --predictions_path gold \
    --split train\
    --config_path swebench/harness/logs/config.json \
    --build_image_only 1
```

## Evaluation

Running evaluations can be resource-intensive. For optimal performance, we recommend the following system specifications:

- **Architecture:** x86_64
- **Storage:** At least 120GB of free space
- **RAM:** 16GB or more
- **CPU:** 8 cores or more

Running fast evaluations on Rust-bench can be resource intensive. We recommend running the evaluation harness on an `x86_64`machine with at least 120GB of free storage, 16GB of RAM, and 8 CPU cores. You may need to experiment with the `--max_workers` argument to find the optimal number of workers for your machine, but we recommend using fewer than `min(0.75 * os.cpu_count(), 24)`.

```
# Run the evaluation harness
python -m swebench.harness.run_evaluation \
    --dataset_name user2f86/rustbench \
    --predictions_path <path_to_your_predictions> \
    --max_workers <num_workers> \
    --run_id <your_run_id>
```

This command generates Docker build logs (`logs/build_images`) and evaluation logs (`logs/run_evaluation`). The final results are stored in the `evaluation_results/` directory.

## RustForger

```bash
conda create -n rustforger python=3.11
conda activate rustforger
pip install langchain langchain-openai openai langchain_community loguru docker
cd ./rustbench_study/RustForger

python3 ./src/docker_handler.py
```

# Implementation & Design of RustForger

### Agent Design and Workflow

- The implementation for the agent's function call API is located in `./rustbench_study/RustForger/src/agent_api.py`.
- The definition of the agent's prompt can be found in `./rustbench_study/RustForger/src/agent_prompt.py`.

---

### Core Implementation and Architecture

- **Modular `Trace` Command:** The core functionality is encapsulated in the `Trace` command, which consists of three modular Rust components totaling approximately 5000 lines of code.
- **AST-based Instrumentation:** It uses the `syn` crate for parsing Rust code and the `quote` crate for code generation, allowing for precise macro injection into the target source code.
- **Concurrent Tracing Runtime:** The tracing runtime handles concurrent execution contexts by maintaining thread-local call stacks and uses `serde_json` for serializing traced data types.
- **Selective Instrumentation:** The tool is designed to instrument regular functions and methods while automatically excluding closures, macros, and test functions to minimize overhead and avoid conflicts.
- **Unified Command-Line Interface:** A single, self-contained binary built with `clap` orchestrates the entire workflow, decoupling high-level agent strategy from low-level implementation details.
- **High-Speed Workflow:** The automated process for managing dependencies, instrumenting code, and subsequent cleanup completes in **under a second**.

---

### Robustness and Fault Tolerance

- **Intelligent Error Recovery:** If a specified function name is incorrect or not found, the tool uses similarity algorithms (e.g., Levenshtein distance) to suggest the most likely correct function names.
- **Panic-Safe Execution:** The system is designed to preserve all collected trace data even if the instrumented program panics, distinguishing between unexpected runtime errors and intentional panics. Example can be seen in `./material/RustAgent_clap-rs__clap-2587.traj` .
- **Automated Backup and Restore:** Before modifying any code, the tool automatically creates backup `.rs.bak` files, ensuring project integrity by enabling automatic rollback upon cleanup.
- **Structured Reporting:** It generates concise, tree-structured trace reports with intelligent formatting and type simplification to facilitate rapid analysis.
- **Atomic Operation:** A unified `run-flow` command orchestrates setup, instrumentation, execution, verification, and cleanup as a single, atomic operation to ensure system stability.
- **Further Details:** Comprehensive implementation details are available in `./rustbench_study/RustForger/rustforger-tracer/README.md`.

## Evaluation Result

All results from our study and evaluation are available in the `/rustbench_study/patch` and `/rustbench_study/eval_reports` directories.

# Benchmark Construction

This command is the initial data preparation step. It's designed to fetch specific version information for your tasks.

```
python versioning/get_versions.py \
    --instances_path <repo>-task-instances.jsonl \
    --retrieval_method github \
    --num_workers 8 \
    --output_dir <output_dir> \
    --cleanup
```

This command is used for **post-processing** tasks. It **updates** the `environment_setup_commit` and the `updated` timestamp for those tasks.

```
python versioning/environment_setup_commit.py \
    --dataset_name repo_versions.json \
    --output_dir <output_dir>
```

This command is the core evaluation step. It runs the actual validation process for the prepared tasks, typically involving applying gold patches and running tests to determine success or failure.

```
python harness/run_validation.py \
    --dataset <repo_versions.json> \
    --run_id <repo_gold> \
    --max_workers 8 \
    --cache_level instance \
    --output_dir <output_dir>
```

## Baseline agents

For detailed commands, please refer to the `README` files in the respective agent repositories.

### Agentless

```python
cd Agentless
# build env
conda create -n agentless python=3.11
conda activate agentless
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:$(pwd)

# run infer
bash ./script/run.sh
```

### Openhands

```python
cd OpenHands
# build env
conda create -n openhands python=3.12 conda-forge::nodejs conda-forge::poetry
conda activate openhands
make build
# run infer
bash evaluation/benchmarks/swe_bench/infer.sh
```

### SWE-agent

```python
cd SWE-agent
conda env create -f environment.yml
conda activate swe-agent

python3 run.py \
   --model_name gpt4o \
   --cache_task_images True \
   --per_instance_api_calls_limit 50 \
   --pre_build_all_images True \ 
   --remove_image False \ 
   --pr_file data/rust_verified.jsonl \ 
   --config_file config/default.yaml  --skip_existing=True \
   --per_instance_cost_limit 4.00 \
   --print_config=False \
   --max_workers_build_image 16
```

### AutoCodeRover

```python
cd auto-code-rover
conda env create -f environment.yml
conda activate auto-code-rover
./run_acr.sh
```

**Prompt adoption file path**:

`openHands/evaluation/benchmarks/swe_bench/run_infer.py`

`SWE-agent/config/default.yaml`

`auto-code-rover/app/agents/*.py`

`agentLess/agentless/multilang/const.py`

## Manually Review 500 tasks

Our dataset, sourced from `user2f86/raw_dataset` on Hugging Face, undergoes a rigorous quality control process. We meticulously screen each instance based on three key criteria:

1. **Solution Leakage:** We check for any direct or indirect exposure of the solution within the problem description.
2. **Problem Description Clarity:** We assess how clear and unambiguous the problem statement is, ensuring it's easy to understand.
3. **Test Validity:** We verify the effectiveness and correctness of the provided test cases to ensure they accurately evaluate potential solutions.

Based on the scores from these three aspects, each instance is categorized in `./material/instances.xlsx` as one of the following:

- **Selected:** These instances meet our highest quality standards and are chosen for the final dataset.
- **Candidate:** These instances are of acceptable quality but aren't optimal. They may be considered for future iterations or specific use cases.
- **Rejected:** These instances do not meet our minimum quality requirements and are excluded from the dataset.

The meticulously curated and refined dataset is finally made available at `user2f86/rustbench` on Hugging Face.  

## Reproduction Stage:

### Agentless/AutoCodeRover Reproduction Stage

```bash
conda activate rustforger
cd ./rustbench_study/reproduce/acr-agentless-reproduce
python3 ./src/rta_main.py
```

To automate the reproduction of reported bugs in Rust projects using a Large Language Model (LLM). The source code for reproducing the work on AutoCodeRover and Agentless is available in the `./reproduce/acr-agentless-reproduce` directory.

- **Core Mechanism:** The main script, `rta_main.py`, initiates the process by feeding a detailed bug report to the LLM.
- **Interaction & Tooling:**
    - Custom prompts, defined in `rta_prompt_acr.py` and `rta_prompt_agentless.py`, guide the LLM's behavior.
    - These prompts instruct the model to utilize a provided toolset—such as `execute_bash` for command execution and `new_file` for file creation—to interact with Rust's complex dependency environment.
- **Outcome:** The LLM generates a sequence of commands to construct a minimal, standalone test case that successfully replicates the target bug, submitting its final findings in a `test_report`.

### Replay Reproduction Stage

```markdown
# 1. Environment Preparation
conda create -n replay python=3.12
conda activate replay
cd replay/dependencies/OpenHands && pip install . && cd -
cd replay/dependencies/SWE-agent && pip install -r requirements.txt && cd -
pip install -r requirements.txt

# 2. Replay Trajectories
bash replay.sh
```

- **Workflow Initiation:** The process commences by extracting the precise reproduction commands from the execution trajectories of an AI agent.
- **Command Integration:** These extracted commands are subsequently merged with the original command sequence to facilitate a complete and authentic replay.
- **Execution Environment:** The full command replay is executed within the agent's native environment, typically encapsulated within a Docker container.
- **Data Capture:** During the replay process, critical execution artifacts are captured for each command, including standard output (stdout), standard error (stderr), and the final exit code.
- **Detailed Documentation:** For comprehensive instructions and advanced usage, please consult the `README.md` file located in the `reproduce/reproduction-replay/` directory.

