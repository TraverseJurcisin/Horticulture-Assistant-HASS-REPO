"""Nutrient toxicity threshold helpers."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_toxicity_thresholds.json"

# Loaded once using cached loader
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_toxicity_thresholds",
    "check_toxicities",
]


def list_supported_plants() -> list[str]:
    """Return plant types with specific toxicity data."""
    return sorted(k for k in _DATA.keys() if k != "default")


def get_toxicity_thresholds(plant_type: str) -> Dict[str, float]:
    """Return toxicity thresholds for ``plant_type`` or defaults."""
    plant = _DATA.get(normalize_key(plant_type))
    if plant is None:
        plant = _DATA.get("default", {})
    return plant if isinstance(plant, dict) else {}


def check_toxicities(current_levels: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return nutrient amounts exceeding toxicity thresholds."""
    thresholds = get_toxicity_thresholds(plant_type)
    toxic: Dict[str, float] = {}
    for nutrient, limit in thresholds.items():
        try:
            level = float(current_levels.get(nutrient, 0))
            excess = level - float(limit)
        except (TypeError, ValueError):
            continue
        if excess > 0:
            toxic[nutrient] = round(excess, 2)
    return toxic
