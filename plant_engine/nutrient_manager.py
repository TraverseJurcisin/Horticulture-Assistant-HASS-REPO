"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict
import os
from functools import lru_cache
from .utils import load_json

DATA_PATH = os.path.join("data", "nutrient_guidelines.json")


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, Dict[str, float]]]:
    if not os.path.exists(DATA_PATH):
        return {}
    return load_json(DATA_PATH)


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for the given plant type and stage."""
    return _load_data().get(plant_type, {}).get(stage, {})


def calculate_deficiencies(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient deficiencies compared to guidelines.

    Only nutrients below the recommended level are returned with the amount
    needed (ppm) to reach the target.
    """

    recommended = get_recommended_levels(plant_type, stage)
    deficiencies: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        current = current_levels.get(nutrient, 0.0)
        diff = round(target - current, 2)
        if diff > 0:
            deficiencies[nutrient] = diff
    return deficiencies
