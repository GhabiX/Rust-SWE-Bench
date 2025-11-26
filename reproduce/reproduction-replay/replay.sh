#!/bin/bash

INPUT_DIR="./data"
OUTPUT_DIR="./result"

INSTANCE_ID="ast-grep__ast-grep-1707"
INSTANCE_METHOD="SWE-agent" # One of ["OpenHands", "SWE-agent", "RustAgent"]
INSTANCE_MODEL="claude" # This is not a critical param, only serves as an identifier

COMMAND="echo 'hello world'"

python -m replay.run \
    --instance-id "${INSTANCE_ID}" \
    --instance-method "${INSTANCE_METHOD}" \
    --instance-model "${INSTANCE_MODEL}" \
    --instance-traj-path "${INPUT_DIR}/${INSTANCE_METHOD}/${INSTANCE_MODEL}/${INSTANCE_ID}.traj" \
    --save-dir "${OUTPUT_DIR}" \
    --command "${COMMAND}"