"""Utilities for managing pending threshold updates."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import get_pending_dir, load_json, save_json

_LOGGER = logging.getLogger(__name__)

PENDING_DIR = get_pending_dir()

__all__ = [
    "queue_threshold_updates",
    "apply_approved_thresholds",
    "list_pending_changes",
    "ThresholdChange",
    "ThresholdUpdateRecord",
]


@dataclass
class ThresholdChange:
    """Single threshold change proposal."""

    previous_value: Any
    proposed_value: Any
    status: str = "pending"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ThresholdUpdateRecord:
    """Container for pending threshold updates."""

    plant_id: str
    timestamp: str
    changes: dict[str, ThresholdChange]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plant_id": self.plant_id,
            "timestamp": self.timestamp,
            "changes": {k: c.as_dict() for k, c in self.changes.items()},
        }


def queue_threshold_updates(
    plant_id: str,
    old: Mapping[str, Any],
    new: Mapping[str, Any],
    base_dir: Path | None = None,
) -> Path:
    """Queue updates by writing a pending file and return its path.

    ``old`` and ``new`` are dictionaries mapping threshold names to values. Any
    differences are stored in ``base_dir`` (defaults to
    :func:`get_pending_dir`).
    """

    directory = base_dir or PENDING_DIR
    directory.mkdir(parents=True, exist_ok=True)
    pending_file = directory / f"{plant_id}.json"

    changes: dict[str, ThresholdChange] = {}
    for key, value in new.items():
        if key not in old or old[key] != value:
            changes[key] = ThresholdChange(previous_value=old.get(key), proposed_value=value)

    record = ThresholdUpdateRecord(
        plant_id=plant_id,
        timestamp=datetime.now().isoformat(),
        changes=changes,
    )

    save_json(pending_file, record.as_dict())

    _LOGGER.info("Queued %d threshold changes for %s", len(changes), plant_id)
    return pending_file


def apply_approved_thresholds(plant_path: str | Path, pending_file: str | Path) -> int:
    """Apply approved threshold changes to ``plant_path`` and return count.

    If ``pending_file`` or ``plant_path`` does not exist the function logs an
    error and returns ``0`` instead of raising an exception.
    """

    plant_p = Path(plant_path)
    pending_p = Path(pending_file)

    if not pending_p.is_file():
        _LOGGER.error("Pending threshold file not found: %s", pending_p)
        return 0
    if not plant_p.is_file():
        _LOGGER.error("Plant profile not found: %s", plant_p)
        return 0

    pending = load_json(pending_p)

    plant = load_json(plant_p)
    updated = plant.get("thresholds", {})

    applied = 0
    for k, change in pending["changes"].items():
        if change.get("status") == "approved":
            updated[k] = change["proposed_value"]
            applied += 1

    plant["thresholds"] = updated
    save_json(plant_p, plant)

    _LOGGER.info("Applied %d approved changes for %s", applied, pending.get("plant_id"))
    return applied


def list_pending_changes(plant_id: str, base_dir: Path | None = None) -> dict[str, Any] | None:
    """Return pending change mapping for ``plant_id`` if a record exists."""

    directory = base_dir or PENDING_DIR
    path = directory / f"{plant_id}.json"
    if not path.exists():
        return None
    return load_json(path)
