import json
from datetime import datetime

_entries = []
_summary = {"applied": [], "skipped": [], "failed": []}
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

def record_outcome(outcome, title, company):
    """Record a job outcome — 'applied', 'skipped', or 'failed'."""
    _summary[outcome].append(f"{title} at {company}")

def clear():
    _entries.clear()
    _summary["applied"].clear()
    _summary["skipped"].clear()
    _summary["failed"].clear()

def flush():
    try:
        output = {
            "summary": {
                "applied": len(_summary["applied"]),
                "skipped": len(_summary["skipped"]),
                "failed":  len(_summary["failed"]),
                "jobs":    _summary,
            },
            "log": _entries,
        }
        with open(DEBUG_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
    except Exception as e:
        print(f"Could not write {DEBUG_FILE}: {e}")

