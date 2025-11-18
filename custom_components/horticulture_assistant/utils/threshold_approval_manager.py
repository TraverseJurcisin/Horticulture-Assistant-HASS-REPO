# File: custom_components/horticulture_assistant/utils/threshold_approval_manager.py

"""Helpers for applying approved threshold changes to plant profiles."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.horticulture_assistant.profile.compat import sync_thresholds
from custom_components.horticulture_assistant.utils.path_utils import data_path, plants_path

from .json_io import load_json as _strict_load_json
from .json_io import save_json as _strict_save_json

_LOGGER = logging.getLogger(__name__)


def _load_json(path: str | Path) -> Any:
    """Return parsed JSON from ``path`` or ``None`` if loading fails."""

    try:
        return _strict_load_json(str(path))
    except FileNotFoundError:
        return None
    except ValueError as exc:
        _LOGGER.error("Invalid JSON in %s: %s", path, exc)
        return None


def _load_pending(path: str) -> tuple[dict[str, Any], Any]:
    """Return normalized mapping of pending approvals and the raw data."""

    data = _load_json(path)
    if not data:
        return {}, data
    if isinstance(data, list):
        out: dict[str, Any] = {}
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


def _save_json(path: str | Path, data: Any) -> None:
    """Write ``data`` to ``path`` creating parent directories."""

    _strict_save_json(str(path), data)


def _serialize_pending(pending: dict[str, Any], original: Any) -> Any:
    """Return ``pending`` converted to the same structure as ``original``.

    ``pending`` is stored as a mapping keyed by plant ID internally but the
    on-disk representation may be a list of entries or a single object. This
    helper ensures the updated mapping is written back in the same format it was
    loaded from so tooling using either style continues to work.
    """

    if isinstance(original, list):
        return list(pending.values())
    if isinstance(original, dict) and any(k in original for k in ("plant_id", "changes", "timestamp")):
        return next(iter(pending.values()), {})
    return pending


def apply_threshold_approvals(hass: HomeAssistant | None = None) -> int:
    """Apply approved threshold changes from ``pending_approvals.json``.

    Returns the number of threshold values that were updated across all
    plant profiles. The location of ``pending_approvals.json`` and the plant
    profiles directory are derived from ``hass`` when provided, mirroring the
    path helpers used by the integration.
    """
    base_data_dir = Path(data_path(hass))
    base_plants_dir = Path(plants_path(hass))
    pending_file_path = base_data_dir / "pending_approvals.json"
    pending_dict, pending_data = _load_pending(pending_file_path)
    if not pending_dict:
        _LOGGER.info("No pending approvals found at %s", pending_file_path)
        return 0

    changes_applied = 0
    # Iterate through each plant entry and apply approved changes
    for plant_id, entry in list(pending_dict.items()):
        changes = entry.get("changes")
        if not changes:
            # No changes listed for this plant, skip it
            _LOGGER.info("No pending threshold changes for plant %s; skipping.", plant_id)
            continue

        plant_file_path = base_plants_dir / f"{plant_id}.json"
        profile = _load_json(plant_file_path)
        if not isinstance(profile, dict):
            _LOGGER.error(
                "Plant profile file not found or invalid for '%s' at %s; skipping these changes.",
                plant_id,
                plant_file_path,
            )
            # Do not remove these changes so they can be applied later when profile exists
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
            _LOGGER.info(
                "Applied approved threshold change for plant %s: %s from %s to %s",
                plant_id,
                nutrient,
                old_val,
                new_val,
            )
            applied_this_plant += 1

        if applied_this_plant == 0:
            # No changes applied (should not happen if we had approved_nutrients), skip to next
            continue

        # Save updated thresholds back to the plant profile file
        profile["thresholds"] = thresholds
        sync_thresholds(profile, default_source="approval", touched_keys=approved_nutrients)
        try:
            _save_json(plant_file_path, profile)
        except Exception as e:  # pragma: no cover - unexpected errors
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
        output_data = _serialize_pending(pending_dict, pending_data)
        _save_json(pending_file_path, output_data)
    except Exception as e:  # pragma: no cover - unexpected errors
        _LOGGER.error("Failed to update pending approvals file: %s", e)
    else:
        if changes_applied:
            _LOGGER.info(
                "Threshold approval processing complete - applied %d change(s). Pending approvals file updated.",
                changes_applied,
            )
        else:
            _LOGGER.info(
                "No approved threshold changes were applied. Pending approvals file updated with no changes removed."
            )

    return changes_applied
