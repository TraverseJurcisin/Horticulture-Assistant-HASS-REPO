import json
import logging
from datetime import datetime
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def push_to_approval_queue(plant_id: str, proposed_thresholds: dict, base_path: str) -> dict:
    """
    Save proposed threshold changes for a plant to a pending approval file.
    
    Loads the current plant profile from `plants/<plant_id>.json` under the given base path, 
    compares its current threshold values to the proposed_thresholds, and records any differences.
    Each changed threshold is recorded with its previous value, proposed value, and a status of "pending".
    The changes are saved to a JSON file in `data/pending_thresholds` named `{plant_id}_{YYYY-MM-DD}.json` 
    (using the current date). If a file for that plant and date already exists, it will be overwritten.
    
    :param plant_id: Identifier of the plant whose thresholds are being updated.
    :param proposed_thresholds: A dictionary of proposed threshold values for the plant.
    :param base_path: Base directory path that contains the "plants" and "data/pending_thresholds" directories.
    :return: A dictionary containing the full set of changes (including previous and proposed values and status).
    """
    base_dir = Path(base_path)
    plant_profile_path = base_dir / "plants" / f"{plant_id}.json"
    try:
        with open(plant_profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
    except Exception as e:
        _LOGGER.error("Failed to load profile for plant '%s': %s", plant_id, e)
        return {}
    
    current_thresholds = profile.get("thresholds", {})
    changes = {}
    # Identify threshold differences
    for key, proposed_value in proposed_thresholds.items():
        previous_value = current_thresholds.get(key)
        if previous_value != proposed_value:
            changes[key] = {
                "previous_value": previous_value,
                "proposed_value": proposed_value,
                "status": "pending"
            }
    
    record = {
        "plant_id": plant_id,
        "timestamp": datetime.utcnow().isoformat(),
        "changes": changes
    }
    
    # Write the record to the pending thresholds file for today
    pending_dir = base_dir / "data" / "pending_thresholds"
    pending_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.utcnow().date()  # current date
    pending_file_path = pending_dir / f"{plant_id}_{date_str}.json"
    try:
        with open(pending_file_path, 'w', encoding='utf-8') as f:
            json.dump(record, f, indent=2)
    except Exception as e:
        _LOGGER.error("Failed to write pending thresholds for plant '%s': %s", plant_id, e)
    
    return record