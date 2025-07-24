"""Soil nutrient target and analysis helpers."""

from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "soil_nutrient_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_soil_targets",
    "calculate_soil_deficiencies",
    "calculate_soil_surplus",
    "score_soil_nutrients",
    "calculate_soil_balance",
]


def list_supported_plants() -> list[str]:
    """Return plant types with soil nutrient guidelines."""
    return list_dataset_entries(_DATA)


def get_soil_targets(plant_type: str) -> Dict[str, float]:
    """Return soil nutrient targets for ``plant_type``."""
    entry = _DATA.get(normalize_key(plant_type), {})
    result: Dict[str, float] = {}
    for k, v in entry.items():
        try:
            result[k] = float(v)
        except (TypeError, ValueError):
            continue
    return result


def calculate_soil_deficiencies(levels: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return nutrient amounts needed to reach soil targets."""
    targets = get_soil_targets(plant_type)
    deficits: Dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        diff = round(target - current, 2)
        if diff > 0:
            deficits[nutrient] = diff
    return deficits


def calculate_soil_surplus(levels: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return amounts exceeding soil targets."""
    targets = get_soil_targets(plant_type)
    surplus: Dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            continue
        diff = round(current - target, 2)
        if diff > 0:
            surplus[nutrient] = diff
    return surplus


def score_soil_nutrients(levels: Mapping[str, float], plant_type: str) -> float:
    """Return a 0-100 score for soil nutrient balance."""
    targets = get_soil_targets(plant_type)
    if not targets:
        return 0.0
    total = 0.0
    count = 0
    for nutrient, target in targets.items():
        if target <= 0:
            continue
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        ratio = abs(current - target) / target
        total += max(0.0, 1 - ratio)
        count += 1
    if count == 0:
        return 0.0
    return round((total / count) * 100, 1)


def calculate_soil_balance(levels: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return ratio of current to target soil nutrient levels."""

    targets = get_soil_targets(plant_type)
    if not targets:
        return {}

    balance: Dict[str, float] = {}
    for nutrient, target in targets.items():
        if target <= 0:
            continue
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        balance[nutrient] = round(current / target, 2)

    return balance
