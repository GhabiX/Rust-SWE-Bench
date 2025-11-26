#!/usr/bin/env bash

# If you'd like to parallelize, do the following:
# * Create a .env file in this folder
# * Declare GITHUB_TOKENS=token1,token2,token3...

python get_tasks_pipeline.py \
    --repos '' \
    --path_prs '' \
    --path_tasks ''\
    --mode new
