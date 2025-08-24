"""Soil nutrient target and analysis helpers."""

from __future__ import annotations

from collections.abc import Mapping

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "soil/soil_nutrient_guidelines.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

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


def get_soil_targets(plant_type: str) -> dict[str, float]:
    """Return soil nutrient targets for ``plant_type``."""
    entry = _DATA.get(normalize_key(plant_type), {})
    result: dict[str, float] = {}
    for k, v in entry.items():
        try:
            result[k] = float(v)
        except (TypeError, ValueError):
            continue
    return result


def calculate_soil_deficiencies(levels: Mapping[str, float], plant_type: str) -> dict[str, float]:
    """Return nutrient amounts needed to reach soil targets."""
    targets = get_soil_targets(plant_type)
    deficits: dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        diff = round(target - current, 2)
        if diff > 0:
            deficits[nutrient] = diff
    return deficits


def calculate_soil_surplus(levels: Mapping[str, float], plant_type: str) -> dict[str, float]:
    """Return amounts exceeding soil targets."""
    targets = get_soil_targets(plant_type)
    surplus: dict[str, float] = {}
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


def calculate_soil_balance(levels: Mapping[str, float], plant_type: str) -> dict[str, float]:
    """Return ratio of current to target soil nutrient levels."""

    targets = get_soil_targets(plant_type)
    if not targets:
        return {}

    balance: dict[str, float] = {}
    for nutrient, target in targets.items():
        if target <= 0:
            continue
        try:
            current = float(levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        balance[nutrient] = round(current / target, 2)

    return balance


def recommend_soil_amendments(
    levels: Mapping[str, float],
    plant_type: str,
    volume_l: float,
    fertilizers: Mapping[str, str],
    purity_overrides: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Return fertilizer grams required to meet soil nutrient targets.

    Parameters
    ----------
    levels : Mapping[str, float]
        Current soil test results in ppm.
    plant_type : str
        Crop identifier for guideline lookup.
    volume_l : float
        Soil volume to amend in liters.
    fertilizers : Mapping[str, str]
        Mapping of nutrient code to fertilizer product id.
    purity_overrides : Mapping[str, float], optional
        Purity fractions overriding values from ``fertilizer_purity.json``.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    deficits = calculate_soil_deficiencies(levels, plant_type)
    if not deficits:
        return {}

    purity_data = load_dataset("fertilizers/fertilizer_purity.json")
    result: dict[str, float] = {}
    for nutrient, ppm_needed in deficits.items():
        fert_id = fertilizers.get(nutrient)
        if not fert_id:
            continue
        purity = None
        if purity_overrides and nutrient in purity_overrides:
            purity = purity_overrides[nutrient]
        else:
            info = purity_data.get(fert_id)
            if isinstance(info, Mapping):
                purity = info.get(nutrient)
        try:
            purity_val = float(purity) if purity is not None else None
        except (TypeError, ValueError):
            purity_val = None
        if purity_val is None or purity_val <= 0:
            continue
        grams = ppm_needed * volume_l / (1000 * purity_val)
        if grams > 0:
            result[fert_id] = round(result.get(fert_id, 0.0) + grams, 2)
    return result


__all__.append("recommend_soil_amendments")
