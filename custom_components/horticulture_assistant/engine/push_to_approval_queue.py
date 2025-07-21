import os
import json
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

def push_to_approval_queue(plant_id: str, proposed_thresholds: dict, base_path: str) -> dict:
    """
    Queue proposed threshold changes for manual approval.

    Loads the current plant profile, compares the proposed thresholds to the current thresholds,
    and records any differences (with status "pending") in a pending thresholds file.
    The changes are saved to data/pending_thresholds/{plant_id}_{YYYY-MM-DD}.json (overwriting any existing file for that date).

    Args:
        plant_id: Identifier of the plant.
        proposed_thresholds: Dictionary of proposed threshold values.
        base_path: Base directory path where "plants" and "data" directories are located.

    Returns:
        A dictionary representing all pending changes (including previous and proposed values and status).
        If no changes are found or an error occurs, returns an empty dict.
    """
    # Determine paths for plant profiles and pending thresholds data
    base_plants_dir = os.path.join(base_path or "", "plants")
    base_data_dir = os.path.join(base_path or "", "data")
    pending_dir = os.path.join(base_data_dir, "pending_thresholds")

    # Load current plant profile
    profile_path = os.path.join(base_plants_dir, f"{plant_id}.json")
    try:
        with open(profile_path, "r", encoding="utf-8") as pf:
            profile = json.load(pf)
    except FileNotFoundError:
        _LOGGER.error("Plant profile for '%s' not found at %s.", plant_id, profile_path)
        return {}
    except json.JSONDecodeError as e:
        _LOGGER.error("Failed to parse profile for plant '%s': %s", plant_id, e)
        return {}

    # Get current thresholds, ensure it's a dict
    current_thresholds = profile.get("thresholds", {})
    if not isinstance(current_thresholds, dict):
        _LOGGER.warning("Thresholds section missing or invalid in profile %s; treating as empty.", plant_id)
        current_thresholds = {}

    # Identify changes between current and proposed thresholds
    changes = {}
    for key, new_value in proposed_thresholds.items():
        old_value = current_thresholds.get(key)
        if key not in current_thresholds or old_value != new_value:
            changes[key] = {
                "previous_value": old_value,
                "proposed_value": new_value,
                "status": "pending"
            }
    if not changes:
        _LOGGER.info("No threshold changes to queue for plant %s (proposed values match current).", plant_id)
        return {}

    # Build record for pending changes
    record = {
        "plant_id": plant_id,
        "timestamp": datetime.now().isoformat(),
        "changes": changes
    }

    # Ensure pending directory exists
    os.makedirs(pending_dir, exist_ok=True)
    # Construct the file path with current date
    date_str = datetime.now().date().isoformat()
    file_name = f"{plant_id}_{date_str}.json"
    file_path = os.path.join(pending_dir, file_name)

    # Save the pending changes to file (overwrite if exists)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
    except Exception as e:
        _LOGGER.error("Failed to save pending thresholds for plant '%s': %s", plant_id, e)
        return {}

    _LOGGER.info("Queued %d threshold change(s) for plant %s (saved to %s)", len(changes), plant_id, file_path)
    for param, info in changes.items():
        _LOGGER.info("Plant %s: pending change - %s: %s -> %s", plant_id, param, info.get("previous_value"), info.get("proposed_value"))

    # Return the full change dictionary
    return record