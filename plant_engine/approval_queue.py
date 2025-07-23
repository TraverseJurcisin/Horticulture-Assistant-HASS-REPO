import logging
import os
from datetime import datetime
from typing import Dict

from .utils import load_json, save_json

_LOGGER = logging.getLogger(__name__)

PENDING_DIR = "data/pending_thresholds"

def queue_threshold_updates(plant_id: str, old: Dict, new: Dict) -> str:
    """Write pending threshold updates for ``plant_id`` and return file path."""

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

    save_json(pending_file, record)

    _LOGGER.info(
        "Queued %d threshold changes for %s", len(record["changes"]), plant_id
    )
    return pending_file

def apply_approved_thresholds(plant_path: str, pending_file: str) -> int:
    """Apply approved threshold changes to ``plant_path`` and return count."""

    pending = load_json(pending_file)

    plant = load_json(plant_path)
    updated = plant["thresholds"]

    applied = 0
    for k, change in pending["changes"].items():
        if change.get("status") == "approved":
            updated[k] = change["proposed_value"]
            applied += 1

    plant["thresholds"] = updated
    save_json(plant_path, plant)

    _LOGGER.info(
        "Applied %d approved changes for %s", applied, pending.get("plant_id")
    )
    return applied

