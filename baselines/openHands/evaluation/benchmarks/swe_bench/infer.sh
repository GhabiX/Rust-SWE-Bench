#!/bin/bash


BASE_SCRIPT="./evaluation/benchmarks/swe_bench/scripts/run_infer.sh"
MODELS=("llm.gpt-4o")
GIT_VERSION="HEAD"
AGENT_NAME="CodeActAgent"
EVAL_LIMIT="500"
MAX_ITER="50"
NUM_WORKERS="1"
LANGUAGE="rust"
DATASET="/data/RustAgent/rustbench_study/baselines/openHands/evaluation/benchmarks/swe_bench/data/rustbench_10.jsonl"



for MODEL in "${MODELS[@]}"; do
    echo "=============================="
    echo "Running benchmark for MODEL: $MODEL"
    echo "=============================="

    $BASE_SCRIPT \
        "$MODEL" \
        "$GIT_VERSION" \
        "$AGENT_NAME" \
        "$EVAL_LIMIT" \
        "$MAX_ITER" \
        "$NUM_WORKERS" \
        "$DATASET" \
        "$LANGUAGE"
    
    echo "Completed $MODEL"
    echo
done