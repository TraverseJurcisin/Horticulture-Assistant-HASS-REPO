"""Wrapper for queuing threshold updates via :mod:`plant_engine`."""

from __future__ import annotations

import logging
from pathlib import Path

from plant_engine.approval_queue import queue_threshold_updates
from plant_engine.utils import get_pending_dir, load_json

_LOGGER = logging.getLogger(__name__)


def push_to_approval_queue(
    plant_id: str, proposed_thresholds: dict, base_path: str | Path = "."
) -> dict:
    """Queue proposed threshold changes for manual approval.

    Parameters
    ----------
    plant_id:
        Identifier of the plant profile to update.
    proposed_thresholds:
        Mapping of threshold keys to new values.
    base_path:
        Root directory containing ``plants`` and ``data`` folders.

    Returns
    -------
    dict
        The pending change record, or an empty mapping if the profile could not
        be loaded.
    """
    base = Path(base_path)
    profile_path = base / "plants" / f"{plant_id}.json"
    try:
        profile = load_json(str(profile_path))
    except Exception as exc:  # pragma: no cover - invalid path or JSON
        _LOGGER.error("Failed to load profile %s: %s", profile_path, exc)
        return {}

    old = profile.get("thresholds", {})
    pending_dir = get_pending_dir(base / "data")
    pending_file = queue_threshold_updates(plant_id, old, proposed_thresholds, pending_dir)
    return load_json(str(pending_file))


__all__ = ["push_to_approval_queue"]
