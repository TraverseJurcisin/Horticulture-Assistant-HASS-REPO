"""Stage-based daily nutrient requirements for crops."""
from __future__ import annotations

from functools import lru_cache
from typing import Mapping, Dict

from plant_engine.constants import get_stage_multiplier
from plant_engine.utils import load_dataset, normalize_key

from .nutrient_requirements import get_requirements

DATA_FILE = "nutrients/stage_nutrient_requirements.json"


@lru_cache(maxsize=None)
def get_stage_requirements(plant_type: str, stage: str) -> Dict[str, float]:
    """Return daily nutrient needs for ``plant_type`` at ``stage``.

    Values are taken from :data:`DATA_FILE` when available. If a stage is
    missing, totals from :func:`get_requirements` are scaled by the stage
    multiplier from :func:`plant_engine.constants.get_stage_multiplier`.
    """

    data = load_dataset(DATA_FILE)
    plant = data.get(normalize_key(plant_type))
    if isinstance(plant, Mapping):
        stage_data = plant.get(normalize_key(stage))
        if isinstance(stage_data, Mapping):
            result: Dict[str, float] = {}
            for nutrient, value in stage_data.items():
                try:
                    result[nutrient] = float(value)
                except (TypeError, ValueError):
                    continue
            return result

    totals = get_requirements(plant_type)
    if not totals:
        return {}

    mult = get_stage_multiplier(stage)
    return {n: round(v * mult, 2) for n, v in totals.items()}


def calculate_stage_deficit(
    current_totals: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return remaining nutrient amounts needed for ``stage``."""

    required = get_stage_requirements(plant_type, stage)
    deficit: Dict[str, float] = {}
    for nutrient, target in required.items():
        try:
            current = float(current_totals.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        diff = round(target - current, 2)
        if diff > 0:
            deficit[nutrient] = diff
    return deficit


__all__ = ["get_stage_requirements", "calculate_stage_deficit"]
