import re
import json
from loguru import logger
import os

def extract_code_blocks(text: str):
    pattern = re.compile(r"```(.*?)```", re.DOTALL)
    blocks = [block.strip() for block in pattern.findall(text)]
    
    # Process each block to remove language identifiers
    cleaned_blocks = []
    for block in blocks:
        # Check if the block starts with a language identifier (e.g., python, bash, rust)
        lines = block.split('\n', 1)
        if len(lines) > 1 and re.match(r'^(python|bash|rust|js|javascript|typescript|ts|go|java|c|cpp|csharp|cs|ruby|php|swift|kotlin|scala|perl|r|shell|powershell|sql|html|css|xml|yaml|json|markdown|md|plaintext)$', lines[0].strip()):
            # Remove the language identifier line and add only the code content
            cleaned_blocks.append(lines[1].strip())
        else:
            cleaned_blocks.append(block.strip())
    
    # Filter to only include function blocks
    function_blocks = [block for block in cleaned_blocks if block.strip().startswith("function:")]
    return function_blocks

def init_logger(log_path: str):
    with open(log_path, 'w') as f:
        pass
    logger.remove()
    logger.add(log_path, level="INFO", encoding="utf-8", enqueue=True, backtrace=True, diagnose=True)
    logger.add(lambda msg: print(msg, end=""), level="INFO")


def log_info(msg: str):
    logger.info(msg)

def log_error(msg: str):
    logger.error(msg)




if __name__ == "__main__":    
    # Test extract_code_blocks function
    test_markdown = '''
Here is a bash code block:
```bash
echo "Hello World"
ls -la
```

Here is a python code block:
```python
def hello():
    print("Hello World")
    return True
```

Here is a function block:
```
function:execute_bash
cmd:ls -la
```

Here is another function block with no language identifier:
```function:str_replace
file_path:/path/to/file.txt
old_str:hello
new_str:world
```
'''
    
    print("Testing code block extraction with language identifier handling:")
    blocks = extract_code_blocks(test_markdown)
    print(f"Found {len(blocks)} function blocks:")
    for i, block in enumerate(blocks, 1):
        print(f"\nBlock {i}:\n{block}")
    
