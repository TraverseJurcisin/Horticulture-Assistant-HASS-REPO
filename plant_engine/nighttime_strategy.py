"""Nighttime optimization guidelines for each plant species."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "nighttime_strategies.json"

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_nighttime_strategy",
    "recommend_nighttime_actions",
]


def list_supported_plants() -> list[str]:
    """Return plant types with nighttime strategy definitions."""
    return list_dataset_entries(_DATA)


def get_nighttime_strategy(plant_type: str) -> Dict[str, object]:
    """Return nighttime strategy mapping for ``plant_type``."""
    return _DATA.get(normalize_key(plant_type), {})


def recommend_nighttime_actions(plant_type: str) -> Dict[str, object]:
    """Return recommended nighttime actions for ``plant_type``."""
    strategy = get_nighttime_strategy(plant_type)
    if not strategy:
        return {}

    actions: Dict[str, object] = {}
    if not strategy.get("irrigate", True):
        actions["skip_irrigation"] = True
    else:
        factor = strategy.get("irrigation_factor")
        if factor is not None:
            actions["irrigation_factor"] = float(factor)

    temp_drop = strategy.get("temperature_drop_c")
    if temp_drop is not None:
        actions["temperature_drop_c"] = float(temp_drop)

    fan_cycles = strategy.get("fan_cycles")
    if fan_cycles:
        actions["fan_cycles"] = str(fan_cycles)

    fert_stop = strategy.get("fertigation_stop_hours")
    if fert_stop is not None:
        actions["fertigation_stop_hours"] = float(fert_stop)

    return actions
