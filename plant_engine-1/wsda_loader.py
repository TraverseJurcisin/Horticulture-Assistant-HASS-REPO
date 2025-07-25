import os
import json
import pandas as pd

WSDA_INDEX_DIR = os.getenv('WSDA_INDEX_DIR', 'data/index_sharded')
WSDA_DETAIL_DIR = os.getenv('WSDA_DETAIL_DIR', 'data/detail')

def stream_index():
    for filename in os.listdir(WSDA_INDEX_DIR):
        if filename.endswith('.jsonl'):
            with open(os.path.join(WSDA_INDEX_DIR, filename), 'r') as file:
                for line in file:
                    yield json.loads(line)

def load_index_df():
    return pd.DataFrame.from_records(stream_index())

def load_detail(product_id):
    prefix = product_id[:2]
    detail_file_path = os.path.join(WSDA_DETAIL_DIR, f"{prefix}/{product_id}.json")
    
    if not os.path.exists(detail_file_path):
        raise FileNotFoundError(f"Detail file not found: {detail_file_path}")
    
    with open(detail_file_path, 'r') as file:
        return json.load(file)