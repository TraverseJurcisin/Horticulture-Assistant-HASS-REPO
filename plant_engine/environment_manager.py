"""Utilities for retrieving and acting on environmental guidelines."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Mapping, Tuple

from .utils import load_dataset

DATA_FILE = "environment_guidelines.json"


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Any]:
    return load_dataset(DATA_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return sorted(_load_data().keys())


def get_environmental_targets(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    data = _load_data().get(plant_type, {})
    if stage:
        stage = stage.lower()
        if stage in data:
            return data[stage]
    return data.get("optimal", {})


def _check_range(value: float, bounds: Tuple[float, float]) -> str | None:
    """Return 'increase' or 'decrease' if value is outside bounds."""
    low, high = bounds
    if value < low:
        return "increase"
    if value > high:
        return "decrease"
    return None


def recommend_environment_adjustments(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return adjustment suggestions for temperature, humidity, light and CO₂."""
    targets = get_environmental_targets(plant_type, stage)
    actions: Dict[str, str] = {}

    if not targets:
        return actions

    mappings = {
        "temp_c": "temperature",
        "humidity_pct": "humidity",
        "light_ppfd": "light",
        "co2_ppm": "co2",
    }

    for key, label in mappings.items():
        if key in targets and key in current:
            suggestion = _check_range(current[key], tuple(targets[key]))
            if suggestion:
                actions[label] = suggestion

    return actions

