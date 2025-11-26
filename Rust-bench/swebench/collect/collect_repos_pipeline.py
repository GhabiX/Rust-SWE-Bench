import json
import os
from get_tasks_pipeline import main as get_tasks_pipeline

def load_json_to_list(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)  
    return data

def set_tokens():
    github_tokens = ""
    with open("tokens", "r") as file:
        a = file.read()
        tokens = a.split("\n")
        github_tokens = ','.join(tokens)
        os.environ['GITHUB_TOKENS'] = github_tokens

if __name__ == '__main__':
    pass


