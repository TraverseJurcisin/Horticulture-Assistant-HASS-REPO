"""Utilities for managing pending threshold updates."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from .utils import load_json, save_json

_LOGGER = logging.getLogger(__name__)

# Default location for queued threshold changes
PENDING_DIR = Path("data/pending_thresholds")
# Environment variable allowing the directory to be customized
PENDING_ENV = "HORTICULTURE_PENDING_DIR"

def get_pending_dir(base: str | Path | None = None) -> Path:
    """Return directory used to store pending threshold files."""

    env = os.getenv(PENDING_ENV)
    if env:
        return Path(env).expanduser()
    if base is not None:
        return Path(base) / "data" / "pending_thresholds"
    return PENDING_DIR

__all__ = [
    "queue_threshold_updates",
    "apply_approved_thresholds",
    "list_pending_changes",
    "get_pending_dir",
    "ThresholdChange",
    "ThresholdUpdateRecord",
]


@dataclass
class ThresholdChange:
    """Single threshold change proposal."""

    previous_value: Any
    proposed_value: Any
    status: str = "pending"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThresholdUpdateRecord:
    """Container for pending threshold updates."""

    plant_id: str
    timestamp: str
    changes: Dict[str, ThresholdChange]

    def as_dict(self) -> Dict[str, Any]:
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
    """Write pending threshold updates and return the file path."""

    directory = Path(base_dir) if base_dir is not None else get_pending_dir()
    directory.mkdir(parents=True, exist_ok=True)
    pending_file = directory / f"{plant_id}.json"

    changes: Dict[str, ThresholdChange] = {}
    for key, value in new.items():
        if key not in old or old[key] != value:
            changes[key] = ThresholdChange(
                previous_value=old.get(key), proposed_value=value
            )

    record = ThresholdUpdateRecord(
        plant_id=plant_id,
        timestamp=datetime.now().isoformat(),
        changes=changes,
    )

    save_json(str(pending_file), record.as_dict())

    _LOGGER.info("Queued %d threshold changes for %s", len(changes), plant_id)
    return pending_file

def apply_approved_thresholds(plant_path: str | Path, pending_file: str | Path) -> int:
    """Apply approved threshold changes to ``plant_path`` and return count."""

    pending = load_json(str(pending_file))

    plant = load_json(str(plant_path))
    updated = plant.get("thresholds", {})

    applied = 0
    for k, change in pending["changes"].items():
        if change.get("status") == "approved":
            updated[k] = change["proposed_value"]
            applied += 1

    plant["thresholds"] = updated
    save_json(str(plant_path), plant)

    _LOGGER.info(
        "Applied %d approved changes for %s", applied, pending.get("plant_id")
    )
    return applied


def list_pending_changes(
    plant_id: str, base_dir: str | Path | None = None
) -> Dict[str, Any] | None:
    """Return pending changes for ``plant_id`` if a record exists."""

    directory = Path(base_dir) if base_dir is not None else get_pending_dir()
    path = directory / f"{plant_id}.json"
    if not path.exists():
        return None
    return load_json(str(path))

