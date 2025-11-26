import json
from pathlib import Path

from agentless.multilang.const import LANGUAGE, LANG_EXT


def process(raw_data):
    raw = json.loads(raw_data)
    data = {
        # 'repo': f'{raw["org"]}/{raw["repo"]}',
        'repo': f'{raw["repo"]}',
        'instance_id': raw['instance_id'],
        # 'base_commit': raw['base']['sha'],
        'base_commit': raw['base_commit'],
        # 'problem_statement': raw['resolved_issues'][0]['title'] + '\n' + raw['resolved_issues'][0]['body'],
        'problem_statement': raw['problem_statement'],
    }
    return data


def load_local_json():
    path = Path(f'data/rustbench.jsonl')
    lines = path.read_text().splitlines()
    dataset = [process(x) for x in lines]
    return dataset


def end_with_ext(file_name):
    for ext in LANG_EXT:
        if file_name.endswith(f'.{ext}'):
            return True
    return False
