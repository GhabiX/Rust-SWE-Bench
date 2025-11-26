#!/bin/bash

MODEL='gpt-4o-2024-11-20'
dataset='rustbench_test'

DATE=$(date '+%Y-%m-%d_%H:%M:%S')

PYTHONPATH=. \
python app/main.py rust-bench \
    --model $MODEL \
    --setup-map /data/RustAgent/rustbench_study/baselines/auto-code-rover/SWE-bench/setup_result/rustbench_test/setup_map.json \
    --tasks-map /data/RustAgent/rustbench_study/baselines/auto-code-rover/SWE-bench/setup_result/rustbench_test/tasks_map.json  \
    --output-dir "EXP/${MODEL}_${dataset}_${DATE}" \
    --num-processes 4 \
    --task-list-file conf/multiswe.txt \
    --conv-round-limit 2\
    --no-print \
    > Logs/${MODEL}_${dataset}_${DATE}.log 2>&1

