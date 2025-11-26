from rta_api import handle_api_call
from rta_utils import extract_code_blocks
import json
import argparse
import os
import subprocess
import re
log_dir = "files"

def main(org: str,repo: str, pr: str):
    file_name = f"rta_log_{org}__{repo}-{pr}.json"
    pr_file = f"/home/reproduce_files/{log_dir}/{file_name}"

    with open(pr_file,"r") as f:
        data = json.loads(f.read())

    messages = data['history']['messages']

    for message in messages:
        # print(message)
        if message['type'] == 'ai':
            print(message['content'])
            code_blocks = extract_code_blocks(message['content'])
            for code_block in code_blocks:
                # print(code_block)
                pattern = r"reproduce_success:[\s\n]+True"
                if re.search(pattern, code_block):
                    print("reproduce_is_successful")
                if "test_file_path" in code_block:
                    parts_after_path_label = code_block.split("test_file_path:")
                    test_file_path = parts_after_path_label[1].split("test_analysis:")[0].strip()
                    result = subprocess.run(
                        ["cat","-n",test_file_path],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minutes
                    )
                    print("FILE_SPLIT_LINE")
                    print(result.stdout)
                    print("FILE_SPLIT_LINE")
                print(handle_api_call(code_block))
                


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("org", type=str, help="Organization name")
    parser.add_argument("repo", type=str, help="Repository name")
    parser.add_argument("pr", type=str, help="Pull request number")
    # parser.add_argument("task_id", type=str, help="Task ID in the format org__repo-pr")
    args = parser.parse_args()
    main(args.org, args.repo, args.pr)