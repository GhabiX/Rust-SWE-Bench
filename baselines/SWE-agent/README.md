
<!-- 注释：以上为Seed官方信息，可直接复制使用，请注意导入"Seed WeChat"（第12行）、"Seed logo"(第20行)图片替换 -->



<!-- 注释：以上为项目基础信息，以项目COMET举例，Comet一级标题（第25行）、徽章Comet名字（第28、30、32、34行）记得替换，徽章可按需使用
请注意，徽章可根据具体项目自定义，如技术成果落地页、技术成果报告/Paper、Hugging Face、项目微信交流群、License、打榜榜单等，更换名字和链接即可；
专属微信群出现在两个位置，第34行、第42行，可以联系EB同学创建 -->
## To Start
### 1. Install
```bash
conda env create -f environment.yml
conda activate mswe-agent
```
### 2. Download Dataset
```bash
sudo chmod +x preprocess_data.sh
./preprocess_data.sh
```

### 3. Run
configure the `keys.cfg` to make sure your OpenAI API key is set correctly.
We provide two ways to run the agent on multi-swe-bench:
#### 3.1 Run serially
```bash
python3 run.py \
   --model_name gpt4o \
   --cache_task_images True \
   --per_instance_api_calls_limit 50 \
   --pre_build_all_images True \ # if you want to build all the images, set it to True, otherwise build case after case
   --remove_image False \ # if you want to remove the image after running, set it to True, otherwise keep it
   --pr_file data/go_verified.jsonl \ # the language you want to run
   --config_file config/default.yaml  --skip_existing=True \
   --per_instance_cost_limit 5.00 \
   --print_config=False \
   --max_workers_build_image 16
```

#### 3.2 Run in parallel
```bash
export RUNNING_THREADS=30
python3 multirun.py \
   --model_name gpt4o \
   --cache_task_images True \
   --per_instance_api_calls_limit 50 \
   --pre_build_all_images True \
   --remove_image False \
   --pr_file data/go.jsonl \
   --config_file config/default.yaml  --skip_existing=True \
   --per_instance_cost_limit 5.00 \
   --print_config=False \
   --max_workers_build_image 16
```

### Images
We provide the images for each instance. You can use the following command to download the images directly from [our docker hub site](https://hub.docker.com/u/mswebench) rather than build them locally.

## 📊 Evaluation
after running the agent, all the predicted patches will be save in `trajactories` directory, named as `all_preds.jsonl`. And then you can evaluate in the [multi-swe-bench](https://github.com/multi-swe-bench/multi-swe-bench) repo

### Run Evaluation

To run the evaluation, you need to prepare the following:

1. Patch Files: Some patch files in JSONL format, each item containing:
   - `org`: Organization Name
   - `repo`: Repository Name
   - `number`: Pull Request Number
   - `fix_patch`: Fix Patch Content
2. Dataset Files: Dataset files in JSONL format available on Hugging Face, such as [Multi-SWE-Bench](https://huggingface.co/datasets/Multi-SWE-RL/Multi-SWE-Bench)

Then you can run the evaluation using the following command:

```bash
cd multi-swe-bench
python -m multi_swe_bench.harness.run_evaluation --config /path/to/your/config.json
```

#### Configuration File Example

```json
{
    "mode": "evaluation",
    "workdir": "./data/workdir",
    "patch_files": [
        "./data/patches/<your_patch_file>.jsonl"
    ],
    "dataset_files": [
        "./data/patches/<to_evaluate_dataset_file>.jsonl"
    ],
    "force_build": false,
    "output_dir": "./data/dataset",
    "specifics": [],
    "skips": [],
    "repo_dir": "./data/repos",
    "need_clone": false,
    "global_env": [],
    "clear_env": true,
    "stop_on_error": true,
    "max_workers": 8,
    "max_workers_build_image": 8,
    "max_workers_run_instance": 8,
    "log_dir": "./data/logs",
    "log_level": "DEBUG"
}
```

#### Configuration Parameters

| Parameter | Description |
|-----------|-------------|
| `mode` | Execution mode for the script. Options: `"evaluation"`, `"instance"`, `"instance_only"`, `"image"`. Default: `"evaluation"` |
| `workdir` | Working directory path for evaluation operations |
| `patch_files` | List of patch file paths in JSONL format (supports glob patterns) |
| `dataset_files` | List of dataset file paths in JSONL format (supports glob patterns) |
| `force_build` | Whether to force rebuild Docker images even if they already exist |
| `output_dir` | Directory path for output results |
| `specifics` | List of specific PR IDs to evaluate (empty = all) |
| `skips` | List of PR IDs to skip during evaluation |
| `repo_dir` | Directory containing cloned repositories |
| `need_clone` | Whether repositories should be cloned if not present |
| `global_env` | Global environment variables to pass to Docker containers (format: `"KEY=VALUE"`) |
| `clear_env` | Whether to clear environment variables in Docker containers |
| `stop_on_error` | Whether to stop execution when an error occurs |
| `max_workers` | Maximum number of concurrent worker threads for general tasks |
| `max_workers_build_image` | Maximum number of concurrent worker threads for building Docker images |
| `max_workers_run_instance` | Maximum number of concurrent worker threads for running instances |
| `log_dir` | Directory for log files |
| `log_level` | Logging level. Options: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` |

## 📜 License
This project is licensed under Apache License 2.0. See the [LICENSE](/LICENSE) flie for details.
## 📖 Citation
If you find XXX useful for your research and applications, feel free to give us a star ⭐ or cite us using:

```bibtex
@article{zan2024swe,
  title={Swe-bench-java: A github issue resolving benchmark for java},
  author={Zan, Daoguang and Huang, Zhirong and Yu, Ailun and Lin, Shaoxin and Shi, Yifan and Liu, Wei and Chen, Dong and Qi, Zongshuai and Yu, Hao and Yu, Lei and others},
  journal={arXiv preprint arXiv:2408.14354},
  year={2024}
}
```
## 🏢 About [ByteDance Seed Team](https://team.doubao.com/)

Founded in 2023, ByteDance Seed Team is dedicated to crafting the industry's most advanced AI foundation models. The team aspires to become a world-class research team and make significant contributions to the advancement of science and society.