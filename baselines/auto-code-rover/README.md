# AutoCodeRover: Autonomous Program Improvement

<br>

<p align="center">
  <img src="https://github.com/nus-apr/auto-code-rover/assets/16000056/8d249b02-1db4-4f58-a5a4-bdb694d65ab1" alt="autocoderover_logo" width="200px" height="200px">
</p>


<p align="center">
  <a href="https://arxiv.org/abs/2404.05427"><strong>ArXiv Paper</strong></a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://autocoderover.dev/"><strong>Website</strong></a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://discord.gg/ScXsdE49JY"><strong>Discord server</strong></a>
</p>

<br>

![overall-workflow](https://github.com/nus-apr/auto-code-rover/assets/48704330/0b8da9ad-588c-4f7d-9c99-53f33d723d35)

<br>


> [!NOTE]
> This is a public version of the AutoCodeRover project. Check the latest results on our [website](https://autocoderover.dev/).

## 🗎 arXiv Paper

For referring to our work, please cite and mention:
```
@inproceedings{zhang2024autocoderover,
    author = {Zhang, Yuntong and Ruan, Haifeng and Fan, Zhiyu and Roychoudhury, Abhik},
    title = {AutoCodeRover: Autonomous Program Improvement},
    year = {2024},
    isbn = {9798400706127},
    publisher = {Association for Computing Machinery},
    address = {New York, NY, USA},
    url = {https://doi.org/10.1145/3650212.3680384},
    doi = {10.1145/3650212.3680384},
    booktitle = {Proceedings of the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis},
    pages = {1592–1604},
    numpages = {13},
    keywords = {automatic program repair, autonomous software engineering, autonomous software improvement, large language model},
    location = {Vienna, Austria},
    series = {ISSTA 2024}
}
```



## 🚀 Setup & Running

### Setup API key and environment


you can have a local copy of AutoCodeRover and manage python dependencies with `environment.yml`.
This is the recommended setup for running rust-bench experiments with AutoCodeRover.
With a working conda installation, do `conda env create -f environment.yml`.
Similarly, set `OPENAI_KEY` or `ANTHROPIC_API_KEY` in your shell before running AutoCodeRover.

```bash
conda env create -f environment.yml
```

## Running AutoCodeRover


### [rust-bench mode] Set up and run on rust-bench tasks

This mode is for running ACR on existing issue tasks contained in rust-bench.

#### Set up

##### Setting up Testbed

For rust-bench mode, we recommend setting up ACR on a host machine, instead of running it in docker mode.

Firstly, set up the rust-bench task instances locally.

1. Clone [this rust-bench fork](https://github.com/yuntongzhang/rust-bench) and follow the [installation instruction](https://github.com/yuntongzhang/rust-bench?tab=readme-ov-file#to-install) to install dependencies.

2. Put the tasks to be run into a file, one per line:

```
cd <rust-bench-path>
echo rinja-rs__askama-788 > tasks.txt
```

Then, set up these tasks by running:
3. Set up these tasks in the file by running:

```
cd <rust-bench-path>
conda activate rust-bench
python harness/run_setup.py --log_dir logs --testbed testbed --result_dir setup_result --subset_file tasks.txt
```

Once the setup for this task is completed, the following two lines will be printed:

```
setup_map is saved to setup_result/setup_map.json
tasks_map is saved to setup_result/tasks_map.json
```

The `testbed` directory will now contain the cloned source code of the target project.
A conda environment will also be created for this task instance.

_If you want to set up multiple tasks together, put multiple ids in `tasks.txt` and follow the same steps._

#### Install rust dependency and build rust tools

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh  
source $HOME/.cargo/env  
cd $(pwd)/rust_parser 
maturin build --release 
pip install $(pwd)/target/wheels/*.whl
```


#### Run a single task in rust-bench

Before running the task (`django__django-11133` here), make sure it has been set up as mentioned [above](#set-up-one-or-more-tasks-in-rust-bench).

```
cd <AutoCodeRover-path>
conda activate auto-code-rover
PYTHONPATH=. python app/main.py rust-bench --model gpt-4o-2024-05-13 --setup-map <rust-bench-path>/setup_result/setup_map.json --tasks-map <rust-bench-path>/setup_result/tasks_map.json --output-dir output --task django__django-11133
```

The output for a run (e.g. for `django__django-11133`) can be found at a location like this: `output/applicable_patch/django__django-11133_yyyy-MM-dd_HH-mm-ss/` (the date-time field in the directory name will be different depending on when the experiment was run).

Path to the final generated patch is written in a file named `selected_patch.json` in the output directory.

#### Run multiple tasks in rust-bench

First, put the id's of all tasks to run in a file, one per line. Suppose this file is `tasks.txt`, the tasks can be run with

```
cd <AutoCodeRover-path>
conda activate auto-code-rover
PYTHONPATH=. python app/main.py rust-bench --model gpt-4o-2024-05-13 --setup-map <rust-bench-path>/setup_result/setup_map.json --tasks-map <rust-bench-path>/setup_result/tasks_map.json --output-dir output --task-list-file <rust-bench-path>/tasks.txt
```

**NOTE**: make sure that the tasks in `tasks.txt` have all been set up in rust-bench. See the steps [above](#set-up-one-or-more-tasks-in-rust-bench).

```bash
./run_acr.sh

```

### Using a different model

AutoCodeRover works with different foundation models. You can set the foundation model to be used with the `--model` command line argument.

The current list of supported models:

|  | Model | AutoCodeRover cmd line argument |
|:--------------:|---------------|--------------|
| OpenAI         | gpt-4o-2024-08-06      | --model gpt-4o-2024-08-06 |
|                | gpt-4o-2024-05-13      | --model gpt-4o-2024-05-13 |
|                | gpt-4-turbo-2024-04-09 | --model gpt-4-turbo-2024-04-09 |
|                | gpt-4-0125-preview     | --model gpt-4-0125-preview |
|                | gpt-4-1106-preview     | --model gpt-4-1106-preview |
|                | gpt-3.5-turbo-0125     | --model gpt-3.5-turbo-0125 |
|                | gpt-3.5-turbo-1106     | --model gpt-3.5-turbo-1106 |
|                | gpt-3.5-turbo-16k-0613 | --model gpt-3.5-turbo-16k-0613 |
|                | gpt-3.5-turbo-0613     | --model gpt-3.5-turbo-0613 |
|                | gpt-4-0613             | --model gpt-4-0613 |
| Anthropic      | Claude 3.5 Sonnet v2   | --model claude-3-5-sonnet-20241022 |
|                | Claude 3.5 Sonnet      | --model claude-3-5-sonnet-20240620 |
|                | Claude 3 Opus          | --model claude-3-opus-20240229 |
|                | Claude 3 Sonnet        | --model claude-3-sonnet-20240229 |
|                | Claude 3 Haiku         | --model claude-3-haiku-20240307 |
| Meta           | Llama 3 70B            | --model llama3:70b |
|                | Llama 3 8B             | --model llama3     |
| AWS Bedrock    | Claude 3 Opus          | --model bedrock/anthropic.claude-3-opus-20240229-v1:0 |
|                | Claude 3 Sonnet        | --model bedrock/anthropic.claude-3-sonnet-20240229-v1:0 |
|                | Claude 3 Haiku         | --model bedrock/anthropic.claude-3-haiku-20240307-v1:0 |
|                | Claude 3.5 Sonnet      | --model bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0 |
|                | Nova Pro               | --model bedrock/us.amazon.nova-pro-v1:0 |
|                | Nova Lite              | --model bedrock/us.amazon.nova-lite-v1:0 |
|                | Nova Micro             | --model bedrock/us.amazon.nova-micro-v1:0 |
| LiteLLM        | Any LiteLLM model      | --model litellm-generic-<MODEL_NAME_HERE> |
| Groq           | Llama 3 8B             | --model groq/llama3-8b-8192 |
|                | Llama 3 70B            | --model groq/llama3-70b-8192 |
|                | Llama 2 70B            | --model groq/llama2-70b-4096 |
|                | Mixtral 8x7B           | --model groq/mixtral-8x7b-32768 |
|                | Gemma 7B               | --model groq/gemma-7b-it |


> [!NOTE]
> Using the Groq models on a free plan can cause the context limit to be exceeded, even on simple issues.

> [!NOTE]
> Some notes on running ACR with local models such as llama3:
> 1. Before using the llama3 models, please [install ollama](https://ollama.com/download/linux) and download the corresponding models with ollama (e.g. `ollama pull llama3`).
> 2. You can run ollama server on the host machine, and ACR in its container. ACR will attempt to communicate to the ollama server on host.
> 3. If your setup is ollama in host + ACR in its container, we recommend installing [Docker Desktop](https://docs.docker.com/desktop/) on the host, in addition to the [Docker Engine](https://docs.docker.com/engine/).
>     - Docker Desktop contains Docker Engine, and also has a virtual machine which makes it easier to access the host ports from within a container. With Docker Desktop, this setup will work without additional effort.
>     - When the docker installation is only Docker Engine, you may need to add either `--net=host` or `--add-host host.docker.internal=host-gateway` to the `docker run` command when starting the ACR container, so that ACR can communicate with the ollama server on the host machine.
> If you encounter any issue in the tool or experiment, you can contact us via email at info@autocoderover.dev, or through our [discord server](https://discord.com/invite/ScXsdE49JY).

## Experiment Replication

Please refer to [EXPERIMENT.md](EXPERIMENT.md) for information on experiment replication.

## ✉️ Contacts

For any queries, you are welcome to open an issue.

Alternatively, contact us at: {[yuntong](https://yuntongzhang.github.io/),[hruan](https://www.linkedin.com/in/haifeng-ruan-701a731a4/),[zhiyufan](https://zhiyufan.github.io/)}@comp.nus.edu.sg.

## Acknowledgements

This work was partially supported by a Singapore Ministry of Education (MoE) Tier 3 grant "Automated Program Repair", MOE-MOET32021-0001.
