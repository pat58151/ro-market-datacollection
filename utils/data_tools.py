import os, json
from datetime import datetime

DATA_FILE = 'item_prices.json'

def load_data():
    """Load historical price data from file"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"เตือน: {DATA_FILE} มีปัญหา จะสร้างใหม่")
            return {}
    return {}

def save_data(data):
    """Save price data to file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

def normalize_item_name(item_name, server_name=None):
    base = item_name.lower().strip()
    if server_name:
        return f"{base}__{server_name.lower().strip()}"
    return base
