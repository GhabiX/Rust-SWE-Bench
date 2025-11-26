import threading
import json
from multi_swe_bench.harness.constant import KEY_INSTANCE_ID
import os

data_registry = dict()
lock = threading.Lock()

def register_data(pr_file):
    global data_registry

    
    current_script_path = os.path.abspath(__file__)
    
    current_directory = os.path.dirname(current_script_path)
    
    relative_file_path = os.path.join('../../', pr_file)
    
    registered_data_path = os.path.join(current_directory, relative_file_path)

    if data_registry is not None and len(data_registry.keys()) > 0:
        print(f"data {registered_data_path} is already registered.")
        return

    
    lock.acquire()
    try:
        
        with open(registered_data_path, "r") as f:
            data_list = [json.loads(line) for line in f]

        data_registry.update({data[KEY_INSTANCE_ID]: data for data in data_list})
    finally:
        
        lock.release()
    print(f"register data {registered_data_path} success.")

def get_data(instance_id: str):
    if data_registry is None or len(data_registry.keys()) == 0:
        register_data()
    data = data_registry.get(instance_id)
    if data is None:
        raise RuntimeError(f"data {instance_id} not found in data registry.")

    return data
