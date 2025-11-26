from pathlib import Path
from datasets import load_dataset
from datetime import datetime
from swebench.utils.dataset_utils import upload_to_huggingface
from datasets import load_dataset
from pandas import Timestamp
import argparse
import os
import requests
import json
# def process_created_at(example):
#     example["created_at"] = convert_created_at(example["created_at"])
#     return example

def get_pr_info(owner, repo, pull_number, access_token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        pr_data = response.json()
        return {
            "created_at": pr_data.get("created_at"),
            "updated_at": pr_data.get("updated_at"),
            "title": pr_data.get("title"),
            "state": pr_data.get("state")
        }
    else:
        print(f"Error: {response.status_code}")
        return None

def add_updated_at(sample):
    owner = sample["repo"].split("/")[0]
    repo = sample["repo"].split("/")[1]
    pull_number = str(sample["pull_number"])
    access_token = os.getenv("GITHUB_TOKEN")
    
    
    result = get_pr_info(owner, repo, pull_number, access_token)
    if result:
        sample["updated_at"] = result["updated_at"]
    else:
        sample["updated_at"] = None  
    
    
    # sample = process_created_at(sample)
    return sample


def main(args):

    dataset_name = args.dataset_name

    if dataset_name.endswith('.json'):
        dataset = load_dataset("json", data_files= dataset_name)['train']
        dataset_name = dataset_name.split('/')[-1].split('.')[0]
    else:
        split = 'train'
        dataset = load_dataset(dataset_name, split=split)

    
    
    def parse_datetime_field(example: dict, field_name: str) -> dict:

        value = example.get(field_name)
        parsed_dt: datetime = None  

        if value is None:
            example[field_name] = None 
            return example
        elif isinstance(value, datetime):
            parsed_dt = value 
        elif isinstance(value, Timestamp): # pandas.Timestamp
            parsed_dt = value.to_pydatetime()
        elif isinstance(value, str):
            try:
                
                parsed_dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                
                
                print(f"Warning: Could not parse string '{value}' for field '{field_name}' to datetime. Setting field to None.")
                example[field_name] = None
                return example 
        else:
            
            print(f"Warning: Unsupported time type '{type(value)}' for field '{field_name}'. Setting field to None.")
            example[field_name] = None
            return example 

        
        if parsed_dt is not None:
            try:
                
                example[field_name] = parsed_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception as e:
                
                print(f"Warning: Could not format datetime object {parsed_dt} for field '{field_name}'. Error: {e}. Setting field to None.")
                example[field_name] = None
        else:
            
            
            example[field_name] = None
            
        return example

    def parse_all_datetime_fields(example):
        example = parse_datetime_field(example, 'created_at')
        example = parse_datetime_field(example, 'updated_at')
        # print("debug:", example['created_at'])
        
        return example

    dataset = dataset.map(add_updated_at)
    dataset = dataset.map(parse_all_datetime_fields)
    
    
    version_to_latest_commit = {}

    for example in dataset:
        if 'version' not in example:
            continue
        version = example['version']
        created_at = example['created_at']
        base_commit = example['base_commit']
        
        
        if (version not in version_to_latest_commit) or (created_at > version_to_latest_commit[version]['created_at']):
            version_to_latest_commit[version] = {
                'base_commit': base_commit,
                'created_at': created_at
            }

    
    version_to_environment_setup_commit = {version: info['base_commit'] for version, info in version_to_latest_commit.items()}

    
    def add_environment_setup_commit(example):
        if 'version' not in example:
            example['environment_setup_commit'] = None
            return example
        version = example['version']
        if version in version_to_environment_setup_commit:
            example['environment_setup_commit'] = version_to_environment_setup_commit[version]
        else:
            example['environment_setup_commit'] = None  
        return example

    
    dataset = dataset.map(add_environment_setup_commit)

    if args.output_dir:
        file_name = args.dataset_name.split('/')[-1]
        file_path = Path(args.output_dir + '/' + file_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        print(args.output_dir)
        print(file_name)
        records_list = [record for record in dataset]
        for x in records_list:
            if 'created_at' in x:
                if isinstance(x['created_at'], Timestamp):
                    x['created_at'] = x['created_at'].strftime("%Y-%m-%dT%H:%M:%SZ")
            if 'updated_at' in x:
                if isinstance(x['updated_at'], Timestamp):
                    x['updated_at'] = x['updated_at'].strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for record in records_list:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            print(f"Dataset saved as a single JSON file to {file_path}")
        except Exception as e:
            print(f"Error saving dataset to JSON file {file_path}: {e}")
        # dataset.to_json(file_path)
        # with file_path.open('w') as f:
        #     f.write(dataset.to_json(orient='records', lines=True))
        # dataset.save_to_disk(args.output_dir)
    else:
        upload_to_huggingface(dataset,dataset_name)
    
    # print("Columns after adding new column:", dataset.column_names)
    # print("First record after adding new column:", dataset[0])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", required=True, type=str, default=None, help="Path to task instances")
    parser.add_argument("--output_dir", required=False, type=str, default=None, help="Path to save the output file")
    args = parser.parse_args()
    main(args)