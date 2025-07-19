import os
import json
from datetime import datetime
from typing import Dict
from plant_engine.utils import load_json, save_json

PENDING_DIR = "data/pending_thresholds"

def queue_threshold_updates(plant_id: str, old: Dict, new: Dict):
    """
    Save proposed threshold changes to a file awaiting manual approval.
    """
    os.makedirs(PENDING_DIR, exist_ok=True)
    pending_file = os.path.join(PENDING_DIR, f"{plant_id}.json")

    record = {
        "plant_id": plant_id,
        "timestamp": datetime.now().isoformat(),
        "changes": {}
    }

    for k in new:
        if k not in old or old[k] != new[k]:
            record["changes"][k] = {
                "previous_value": old.get(k),
                "proposed_value": new[k],
                "status": "pending"
            }

    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    print(f"📝 Queued {len(record['changes'])} threshold changes for {plant_id}")


def apply_approved_thresholds(plant_path: str, pending_file: str):
    """
    Apply approved threshold changes to plant profile.
    """
    with open(pending_file, "r", encoding="utf-8") as f:
        pending = json.load(f)

    plant = load_json(plant_path)
    updated = plant["thresholds"]

    applied = 0
    for k, change in pending["changes"].items():
        if change.get("status") == "approved":
            updated[k] = change["proposed_value"]
            applied += 1

    plant["thresholds"] = updated
    save_json(plant_path, plant)

    print(f"✅ Applied {applied} approved changes for {pending['plant_id']}")
    return applied

