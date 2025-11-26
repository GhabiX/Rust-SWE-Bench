import os
import sys
import json
import argparse


from agent_prompt import rustforger_reproduce_tracing_prompt
from agent_utils import extract_code_blocks, init_logger, log_info, log_error, get_instance_info
from agent_api import handle_api_call
from runtime_config import initialize_context_manager, get_runtime_config

from agent_query_llm import query_llm, init_runnable, get_session_history


def resolve_main_loop(runnable_with_history, prompt_str, session_id, context_config, max_turns=100, max_budget=4.0, warning_budget=3.5):
    """
    Main loop for resolving tasks with both turn-based and cost-based limits.
    
    Args:
        runnable_with_history: The LLM runnable with history
        prompt_str: Initial prompt string
        session_id: Session identifier
        context_config: Context configuration
        max_turns: Maximum number of turns (backup limit)
        max_budget: Maximum budget in USD (primary limit)
        warning_budget: Budget threshold for warnings in USD
    """
    turn_count = 0
    total_cost = 0.0
    task_report = None
    rta_cmd_result = prompt_str
    
    log_info(f"[Budget Config]: Max budget: ${max_budget:.2f}, Warning budget: ${warning_budget:.2f}")
    
    while turn_count < max_turns and total_cost < max_budget:
        try:
            # Call LLM and get response with cost information
            response_data = query_llm(runnable_with_history, rta_cmd_result, session_id=session_id, context_config=context_config)
            
            # Extract response content and cost information
            response = response_data["content"]
            turn_cost = response_data["cost"]
            token_info = response_data["tokens"]
            
            # Update total cost
            total_cost += turn_cost
            
            # Log cost information
            log_info(f"[Cost Info]: Turn cost: ${turn_cost:.6f}, Total cost: ${total_cost:.6f}")
            log_info(f"[Token Info]: Prompt: {token_info['prompt_tokens']}, Completion: {token_info['completion_tokens']}, Total: {token_info['total_tokens']}")

            log_info(f"[Function Result]:\n{rta_cmd_result}")
            log_info('='*100)
            log_info(f"[LLM Response]:\n{response}")

            code_blocks = extract_code_blocks(response)
            
            # Handle case when no code blocks are found in the response
            if not code_blocks:
                log_info("[Exception]: No Function call found in response. All Function calls must be enclosed in a ```\\nfunction:...``` code block.")
                rta_cmd_result = "No Function call found in response. All Function calls must be enclosed in a ```\\nfunction:...``` code block. \
                                     Use the provided Functions to complete the task independently."
                turn_count += 1
                continue
                
            rta_cmd = code_blocks[0]
            # log_info(f"[Function]:\n{rta_cmd}")
            rta_cmd_result = handle_api_call(fr'{rta_cmd}')

            # Check if this is a task_report result
            if rta_cmd.strip().startswith("function:task_report"):
                task_report = json.loads(rta_cmd_result)
                log_info(f"[Task Report Received]: Task completed with success={task_report.get('task_resolve_success', 'False')}")
                break

            # Only add warning when more than one code block is found (fixed bug)
            if len(code_blocks) > 1:
                rta_cmd_result += '\n[Warning]: Only **ONE** Function call is permitted & executed per turn.'
            
            turn_count += 1
            log_info(f"[Progress]: Turn {turn_count}/{max_turns}, Cost: ${total_cost:.6f}/${max_budget:.2f}")
            
            # Budget-based control logic (primary control mechanism)
            if total_cost >= max_budget:
                log_info(f"[Budget Limit]: Maximum budget ${max_budget:.2f} reached. Forcing task_report submission.")
                rta_cmd_result += f'\n[Critical]: Budget limit (${max_budget:.2f}) reached. You MUST submit task_report immediately.'
                break
            elif total_cost >= warning_budget:
                remaining_budget = max_budget - total_cost
                log_info(f"[Budget Warning]: Warning budget ${warning_budget:.2f} reached. Remaining: ${remaining_budget:.2f}")
                rta_cmd_result += f'\n[Attention]: Budget warning! Only ${remaining_budget:.2f} left before limit. Please ready to submit task_report.'
            
            # Turn-based control logic (backup control mechanism)
            elif turn_count > max_turns - 5:
                rta_cmd_result += f'\n[Attention]: Only {max_turns-turn_count} turns left. Please ready to submit task_report'
                
        except Exception as e:
            log_error(f"[Exception]: {str(e)}")
            if "Request timed out" in str(e):
                log_info("[Exception]: Request timed out. Continuing...")
                turn_count += 1
                continue
            break

    # Log final statistics
    log_info(f"[Final Stats]: Total turns: {turn_count}, Total cost: ${total_cost:.6f}")
    if total_cost >= max_budget:
        log_info(f"[Termination]: Stopped due to budget limit (${max_budget:.2f})")
    elif turn_count >= max_turns:
        log_info(f"[Termination]: Stopped due to turn limit ({max_turns})")
    
    return task_report


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='RustForger Agent Runner')
    parser.add_argument('--model', type=str, default="gpt-4o-2024-08-06",
                      help='Model name to use (default: gpt-4o-2024-08-06)')
    parser.add_argument('--instance', type=str, required=True,
                      help='Instance ID to process (e.g., clap-rs__clap_5227)')
    parser.add_argument('--max-turns', type=int, default=None,
                      help='Maximum number of turns (uses system defaults if not specified)')
    
    # Budget control parameters - will override config defaults
    parser.add_argument('--max-budget', type=float, default=None,
                      help='Maximum budget in USD (overrides system defaults)')
    parser.add_argument('--warning-budget', type=float, default=None,
                      help='Budget threshold for warnings in USD (overrides system defaults)')
    

    args = parser.parse_args()
    model_name = args.model
    instance_id = args.instance

    # Initialize system configuration
    runtime_config = get_runtime_config()
    
    # Determine budget limits from config or command line
    config_max_budget, config_warning_budget = runtime_config.get_budget_limits()
    max_budget = args.max_budget if args.max_budget is not None else config_max_budget
    warning_budget = args.warning_budget if args.warning_budget is not None else config_warning_budget
    
    # Determine execution limits
    execution_limits = runtime_config.get_execution_limits()
    max_turns = args.max_turns if args.max_turns is not None else execution_limits.get("max_interaction_cycles", 60)

    # Validate budget parameters
    if warning_budget >= max_budget:
        raise ValueError(f"Warning budget (${warning_budget:.2f}) must be less than max budget (${max_budget:.2f})")

    # Prepare runtime overrides based on command line options
    runtime_overrides = {}

    runtime_overrides['adaptive_trimming'] = True
    
    runtime_overrides.update({
        'recent_window_size': 20,
        'content_preview_head': 15,
        'content_preview_tail': 15
    })

    
    # Initialize context manager with system optimizations
    context_config = initialize_context_manager(runtime_overrides)



    instance_bug_report, instance_workspace_path = get_instance_info(instance_id)
    
    rta_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    log_path = f'{rta_base_dir}/log/rustforger_log_{instance_id}.log'

    init_logger(log_path)
    
    runnable_with_history = init_runnable(instance_workspace_path, model_name, context_config)
    # prompt = rustforger_prompt.format(issue_repo_path=instance_workspace_path, issue_description=instance_bug_report, test_report=test_report)
    prompt = rustforger_reproduce_tracing_prompt.format(issue_repo_path=instance_workspace_path, issue_description=instance_bug_report)
    prompt_str = prompt.replace("{", "{{").replace("}", "}}")

    # Log optimization status based on configuration
    if context_config.enable_trimming:
        log_info("[Memory Optimization Enabled] Using adaptive context management")
    else:
        log_info("[Standard Mode] Using full context retention")

    session_id = "rustforger_session"
    
    # Run main loop with budget control
    task_report = resolve_main_loop(
        runnable_with_history, 
        prompt_str, 
        session_id, 
        context_config, 
        max_turns=max_turns,
        max_budget=max_budget,
        warning_budget=warning_budget
    )
    
    # Save conversation history
    history = get_session_history(session_id)
    
    # Create output dictionary with both history and task_report
    output_data = {
        "history": json.loads(history.model_dump_json()),
        "task_report": task_report,    # Add budget information to output
        "budget_info": {
            "max_budget": max_budget,
            "warning_budget": warning_budget,
            "final_cost": getattr(task_report, 'final_cost', 0) if task_report else 0
        }
    }
    
    # Save combined data to JSON file
    with open(f'{rta_base_dir}/log/rustforger_log_{instance_id}.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, indent=2, ensure_ascii=False, fp=f)

        