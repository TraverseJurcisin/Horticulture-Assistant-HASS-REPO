"""Utilities for retrieving and acting on environmental guidelines."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Mapping

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


def recommend_environment_adjustments(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return simple adjustment suggestions based on current readings."""
    targets = get_environmental_targets(plant_type, stage)
    actions: Dict[str, str] = {}

    if not targets:
        return actions

    if "temp_c" in targets and "temp_c" in current:
        low, high = targets["temp_c"]
        temp = current["temp_c"]
        if temp < low:
            actions["temperature"] = "increase"
        elif temp > high:
            actions["temperature"] = "decrease"

    if "humidity_pct" in targets and "humidity_pct" in current:
        low, high = targets["humidity_pct"]
        hum = current["humidity_pct"]
        if hum < low:
            actions["humidity"] = "increase"
        elif hum > high:
            actions["humidity"] = "decrease"

    return actions

