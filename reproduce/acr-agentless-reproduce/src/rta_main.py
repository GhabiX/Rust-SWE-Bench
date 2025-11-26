import os
import sys
import json
import argparse


# from agent_prompt import rta_user_prompt
from rta_prompt_acr import rta_user_prompt
from agent_utils import extract_code_blocks, init_logger, log_info, log_error, get_instance_info
from agent_api import handle_api_call

from agent_query_llm import query_llm, init_runnable, get_session_history


def reproduce_main_loop(runnable_with_history, prompt_str, session_id):
    round_count = 0
    test_report = None
    rta_cmd_result = prompt_str
    while round_count < 30:
        try:
            response = query_llm(runnable_with_history, rta_cmd_result, session_id=session_id)

            log_info(f"[Function Result]:\n{rta_cmd_result}")
            log_info('='*100)
            log_info(f"[LLM Response]:\n{response}")

            code_blocks = extract_code_blocks(response)
            
            # Handle case when no code blocks are found in the response
            if not code_blocks:
                log_info("[Exception]: No Function call found in response. All Function calls must be enclosed in a ```\\nfunction:...``` code block.")
                rta_cmd_result = "No Function call found in response. All Function calls must be enclosed in a ```\\nfunction:...``` code block. \
                                     Use the provided Functions to complete the task independently."
                round_count += 1
                continue
                
            rta_cmd = code_blocks[0]
            # log_info(f"[Function]:\n{rta_cmd}")
            rta_cmd_result = handle_api_call(rta_cmd)

            # Check if this is a test_report result
            if rta_cmd.strip().startswith("function:test_report"):
                test_report = json.loads(rta_cmd_result)
                # Get success status from reproduce_success parameter
                success_status = test_report.get('reproduce_success', 'False')
                log_info(f"[Test Report Received]: Test completed with success={success_status}")
                break

            # Only add warning when more than one code block is found (fixed bug)
            if len(code_blocks) > 1:
                rta_cmd_result += '\n[Warning]: Only **ONE** Function call is permitted & executed per turn.'
            round_count += 1
            if round_count > 25:
                rta_cmd_result += f'\n[Attention]: Only {30-round_count} turns left. Please ready to submit test_report'
        except Exception as e:
            log_error(f"[Exception]: {str(e)}")
            if "Request timed out" in str(e):
                log_info("[Exception]: Request timed out. Continuing...")
                round_count += 1
                continue
            break

    return test_report


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='RTA Agent Runner')
    parser.add_argument('--model', type=str, default="gpt-4o-2024-08-06",
                      help='Model name to use (default: gpt-4o-2024-08-06)')
    parser.add_argument('--instance', type=str, required=True,
                      help='Instance ID to process (e.g., clap-rs__clap_5527)')
    
    args = parser.parse_args()
    model_name = args.model
    instance_id = args.instance

    instance_bug_report, instance_workspace_path = get_instance_info(instance_id)
    
    rta_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_path = f'{rta_base_dir}/log/rta_log_{instance_id}.log'

    init_logger(log_path)
    
    runnable_with_history = init_runnable(instance_workspace_path, model_name)
    prompt = rta_user_prompt.format(issue_repo_path=instance_workspace_path, issue_description=instance_bug_report)
    prompt_str = prompt.replace("{", "{{").replace("}", "}}")

    session_id = "reproduce_session"
    
    test_report = reproduce_main_loop(runnable_with_history, prompt_str, session_id)
    
    # Save conversation history
    history = get_session_history(session_id)
    
    # Create output dictionary with both history and test_report
    output_data = {
        "history": json.loads(history.model_dump_json()),
        "test_report": test_report
    }
    
    # Save combined data to JSON file
    with open(f'{rta_base_dir}/log/rta_log_{instance_id}.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, indent=2, ensure_ascii=False, fp=f)

        