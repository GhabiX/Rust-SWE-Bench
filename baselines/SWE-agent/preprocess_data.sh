# Make sure git-lfs is installed (https://git-lfs.com)
git lfs install
git clone https://huggingface.co/datasets/bytedance-research/Multi-SWE-Bench data/

# merge all repos of one language into one jsonl
LANGS=(
    'cpp'
    'go'
    'java'
    'js'
    'rust'
    'ts'
    'c'
)
for lang in ${LANGS[@]}; do
    cat data/$lang/*.jsonl > data/$lang.jsonl
done