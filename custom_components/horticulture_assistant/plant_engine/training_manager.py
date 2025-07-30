"""Access plant training guidelines by stage."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "training/training_guidelines.json"

# Loaded once via :func:`load_dataset` which caches results
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "list_training_stages",
    "get_training_guideline",
]


def list_supported_plants() -> list[str]:
    """Return plant types with training guidelines."""
    return list_dataset_entries(_DATA)


def list_training_stages(plant_type: str) -> list[str]:
    """Return stages with training tips for ``plant_type``."""
    plant = _DATA.get(normalize_key(plant_type), {})
    return sorted(plant.keys()) if isinstance(plant, dict) else []


def get_training_guideline(plant_type: str, stage: str) -> str | None:
    """Return training advice for ``plant_type`` at ``stage`` if available."""
    plant = _DATA.get(normalize_key(plant_type), {})
    if not isinstance(plant, dict):
        return None
    guideline = plant.get(normalize_key(stage))
    return str(guideline) if isinstance(guideline, str) else None
