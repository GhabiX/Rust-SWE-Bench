from datasets import load_dataset, Dataset
import json

with open("instance.jsonl", "r") as f:
    dataset = Dataset.from_list([json.loads(line) for line in f])

changed_data = []

for i in range(len(dataset)):
    data = dataset[i]
    new_data = {}
    new_data['org'] = data['repo'].split('/')[0]
    new_data['repo'] = data['repo'].split('/')[1]
    new_data['number'] = data['pull_number']
    new_data['state'] = 'closed'
    new_data['title'] = 'fake'
    new_data['body'] = 'fake'
    new_data['base'] = {
        'label': 'fake',
        'ref': 'fake',
        'sha': data['base_commit'],
    }
    new_data['resolved_issues'] = [{
        'number': data['issue_numbers'][0],
        'title': 'fake',
        'body': data['problem_statement'],
    }]
    new_data['fix_patch'] = data['patch']
    new_data['test_patch'] = data['test_patch']
    new_data['instance_id'] = data['instance_id']
    changed_data.append(new_data)

with open('instance.jsonl', 'w') as f:
    for data in changed_data:
        f.write(json.dumps(data) + '\n')
