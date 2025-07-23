# File: custom_components/horticulture_assistant/utils/threshold_approval_manager.py

"""Helpers for applying approved threshold changes to plant profiles."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Tuple

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_LOGGER = logging.getLogger(__name__)


def _load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            _LOGGER.error("Invalid JSON in %s: %s", path, exc)
            return None


def _load_pending(path: str) -> Tuple[Dict[str, Any], Any]:
    data = _load_json(path)
    if not data:
        return {}, data
    if isinstance(data, list):
        out: Dict[str, Any] = {}
        for entry in data:
            pid = entry.get("plant_id")
            if pid:
                out[pid] = entry
        return out, data
    if isinstance(data, dict) and any(k in data for k in ("plant_id", "changes", "timestamp")):
        pid = data.get("plant_id", "unknown")
        return {pid: data}, data
    if isinstance(data, dict):
        return data, data
    _LOGGER.error("Unexpected format in pending approvals: %s", type(data))
    return {}, data


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _save_pending(path: str, pending: Dict[str, Any], original: Any) -> None:
    if isinstance(original, list):
        data = list(pending.values())
    elif isinstance(original, dict) and any(k in original for k in ("plant_id", "changes", "timestamp")):
        data = next(iter(pending.values()), {})
    else:
        data = pending
    _save_json(path, data)


def apply_threshold_approvals(hass: HomeAssistant = None) -> None:
    """Apply approved threshold changes from pending approvals to plant profiles."""
    base_data_dir = hass.config.path("data") if hass else "data"
    base_plants_dir = hass.config.path("plants") if hass else "plants"
    pending_file_path = os.path.join(base_data_dir, "pending_approvals.json")
    pending_dict, pending_data = _load_pending(pending_file_path)
    if not pending_dict:
        _LOGGER.info("No pending approvals found at %s", pending_file_path)
        return

    changes_applied = 0
    # Iterate through each plant entry and apply approved changes
    for plant_id, entry in list(pending_dict.items()):
        changes = entry.get("changes")
        if not changes:
            # No changes listed for this plant, skip it
            _LOGGER.info("No pending threshold changes for plant %s; skipping.", plant_id)
            continue

        plant_file_path = os.path.join(base_plants_dir, f"{plant_id}.json")
        # Load the plant's profile JSON
        try:
            with open(plant_file_path, "r", encoding="utf-8") as pf:
                profile = json.load(pf)
        except FileNotFoundError:
            _LOGGER.error("Plant profile file not found for '%s' at %s; skipping these changes.", plant_id, plant_file_path)
            # Do not remove these changes so they can be applied later when profile exists
            continue
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to read profile for plant '%s': %s; skipping its changes.", plant_id, e)
            continue

        # Ensure thresholds section exists in profile
        thresholds = profile.get("thresholds")
        if thresholds is None:
            thresholds = {}
        elif not isinstance(thresholds, dict):
            _LOGGER.warning("Unexpected thresholds format in profile %s; resetting to empty dict.", plant_id)
            thresholds = {}

        # Apply all approved changes for this plant
        approved_nutrients = [nut for nut, info in changes.items() if info.get("status") == "approved"]
        if not approved_nutrients:
            # No approved changes for this plant; log and skip (leave pending data unchanged)
            for nut, info in changes.items():
                status = info.get("status", "pending")
                _LOGGER.info("Skipping threshold change for plant %s: %s (status: %s)", plant_id, nut, status)
            continue

        applied_this_plant = 0
        for nutrient in approved_nutrients:
            change = changes.get(nutrient)
            if not change:
                continue
            old_val = change.get("previous_value")
            new_val = change.get("proposed_value")
            thresholds[nutrient] = new_val
            _LOGGER.info("Applied approved threshold change for plant %s: %s from %s to %s", plant_id, nutrient, old_val, new_val)
            applied_this_plant += 1

        if applied_this_plant == 0:
            # No changes applied (should not happen if we had approved_nutrients), skip to next
            continue

        # Save updated thresholds back to the plant profile file
        profile["thresholds"] = thresholds
        try:
            os.makedirs(os.path.dirname(plant_file_path), exist_ok=True)
            with open(plant_file_path, "w", encoding="utf-8") as pf:
                json.dump(profile, pf, indent=2)
        except Exception as e:
            _LOGGER.error("Failed to write updated profile for plant '%s': %s", plant_id, e)
            # Skip removal so the changes can be retried later
            continue

        changes_applied += applied_this_plant
        # Mark these changes as approved and remove them from pending data
        for nutrient in approved_nutrients:
            if nutrient in changes:
                changes[nutrient]["status"] = "approved"
                changes.pop(nutrient, None)
        # If no remaining changes for this plant, remove the plant entry
        if not changes:
            pending_dict.pop(plant_id, None)

    # Write the updated pending approvals back to file (removing applied changes)
    try:
        os.makedirs(os.path.dirname(pending_file_path), exist_ok=True)
        # Determine output structure type (same format as original)
        output_data = None
        if isinstance(pending_data, list):
            # Convert dict back to list of entries
            output_data = list(pending_dict.values())
        elif isinstance(pending_data, dict) and any(k in ("plant_id", "changes", "timestamp") for k in pending_data.keys()):
            # Single record originally
            if pending_dict:
                output_data = next(iter(pending_dict.values()))
            else:
                output_data = {}
        else:
            output_data = pending_dict
        with open(pending_file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
    except Exception as e:
        _LOGGER.error("Failed to update pending approvals file: %s", e)
    else:
        if changes_applied:
            _LOGGER.info("Threshold approval processing complete - applied %d change(s). Pending approvals file updated.", changes_applied)
        else:
            _LOGGER.info("No approved threshold changes were applied. Pending approvals file updated with no changes removed.")
