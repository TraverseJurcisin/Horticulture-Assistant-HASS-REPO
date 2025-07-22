"""Pruning guideline helpers."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "pruning_guidelines.json"

# Loaded once via load_dataset which uses caching
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "list_stages",
    "get_pruning_instructions",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with pruning data."""
    return sorted(_DATA.keys())


def list_stages(plant_type: str) -> list[str]:
    """Return available pruning stages for ``plant_type``."""
    return sorted(_DATA.get(normalize_key(plant_type), {}).keys())


def get_pruning_instructions(plant_type: str, stage: str) -> str:
    """Return pruning instructions for a plant type and stage."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return ""
    return plant.get(normalize_key(stage), "")
