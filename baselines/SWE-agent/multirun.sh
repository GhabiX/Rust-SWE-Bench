unset OPENAI_API_KEY
unset OPENAI_API_BASE_URL

python3 multirun.py \
   --model_name gpt-4o\
   --cache_task_images True \
   --pre_build_all_images False \
   --remove_image False \
   --pr_file data/rust_test.jsonl\
   --config_file config/default.yaml  --skip_existing=True \
   --per_instance_cost_limit 5.00 \
   --print_config=False \
   --max_workers_build_image 4