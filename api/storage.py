import json, os
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def save_json(filename, data):
    file = os.path.join(DATA_DIR, filename)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)



def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    
    

def logger(message):
    logs = load_json("jobs.json")
    logs.append({"time": datetime.now(timezone.utc).isoformat(), "message": message})
    save_json("jobs.json", logs)