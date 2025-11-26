#!/bin/bash


# 1.21
python3 run_validation.py \
    --dataset_name user2f86/rustbench\
    --run_id test\
    --max_workers 10 \
    --cache_level instance \
    --instance_ids kivikakk__comrak-426 \
    --force_rebuild 1
