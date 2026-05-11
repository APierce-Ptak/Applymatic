import json
from datetime import datetime

_entries = []
DEBUG_FILE = "debug.json"

def log(msg, level="INFO"):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "level": level,
        "msg": str(msg),
    }
    _entries.append(entry)
    print(msg)

def error(msg):
    log(msg, level="ERROR")

def clear():
    _entries.clear()

def flush():
    try:
        with open(DEBUG_FILE, "w", encoding="utf-8") as f:
            json.dump(_entries, f, indent=2)
    except Exception as e:
        print(f"Could not write {DEBUG_FILE}: {e}")
