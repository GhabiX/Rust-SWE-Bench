import re
import json
from loguru import logger
import os

def extract_code_blocks(text: str):
    lines = text.split('\n')
    
    code_blocks = []
    current_block = []
    in_code_block = False
    
    for line in lines:
        stripped_line = line.strip()
        
        if stripped_line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                current_block = []
                if len(stripped_line) > 3:
                    language_identifier = stripped_line[3:].strip()
                    if language_identifier:
                        current_block.append(language_identifier)
            else:
                in_code_block = False
                block_content = '\n'.join(current_block).strip()
                if block_content:
                    code_blocks.append(block_content)
                current_block = []
        elif in_code_block:
            current_block.append(line)
    

    cleaned_blocks = []
    for block in code_blocks:

        lines = block.split('\n', 1)
        if len(lines) > 1 and re.match(r'^(python|bash|rust|js|javascript|typescript|ts|go|java|c|cpp|csharp|cs|ruby|php|swift|kotlin|scala|perl|r|shell|powershell|sql|html|css|xml|yaml|json|markdown|md|plaintext)$', lines[0].strip()):

            cleaned_blocks.append(lines[1].strip())
        else:
            cleaned_blocks.append(block.strip())
    
    function_blocks = [block for block in cleaned_blocks if block.strip().startswith("function:")]
    return function_blocks

def init_logger(log_path: str):
    with open(log_path, 'w') as f:
        pass
    logger.remove()
    logger.add(log_path, level="INFO", encoding="utf-8", enqueue=True, backtrace=True, diagnose=True)
    # logger.add(lambda msg: print(msg, end=""), level="INFO")


def log_info(msg: str):
    logger.info(msg)

def log_error(msg: str):
    logger.error(msg)


def get_instance_info(instance_id: str):
    instance_workspace_path = '/workspace/' + re.sub(r'-\d+$', '', instance_id) +  "__0.1" 
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file_path = os.path.join(os.path.dirname(current_dir), 'data', 'rb_all_bug_report.json')
    with open(data_file_path, 'r') as f:
        bugreport_dataset = json.load(f)
        if instance_id not in bugreport_dataset:
            raise Exception(f"Instance ID {instance_id} not found in bug report dataset")
        instance_bug_report = bugreport_dataset[instance_id]
        return instance_bug_report, instance_workspace_path
