from __future__ import annotations

"""Pest monitoring utilities using threshold datasets."""

from typing import Dict, Mapping

from .utils import load_dataset
from .pest_manager import recommend_treatments, get_beneficial_insects

DATA_FILE = "pest_thresholds.json"

# Load once with caching
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)

__all__ = [
    "get_pest_thresholds",
    "assess_pest_pressure",
    "recommend_threshold_actions",
    "recommend_ipm_plan",
]


def get_pest_thresholds(plant_type: str) -> Dict[str, int]:
    """Return pest count thresholds for ``plant_type``."""
    return _THRESHOLDS.get(plant_type, {})


def assess_pest_pressure(plant_type: str, observations: Mapping[str, int]) -> Dict[str, bool]:
    """Return mapping of pests to ``True`` if threshold exceeded."""
    thresholds = get_pest_thresholds(plant_type)
    pressure: Dict[str, bool] = {}
    for pest, count in observations.items():
        thresh = thresholds.get(pest)
        if thresh is None:
            continue
        pressure[pest] = count >= thresh
    return pressure


def recommend_threshold_actions(plant_type: str, observations: Mapping[str, int]) -> Dict[str, str]:
    """Return treatment actions for pests exceeding thresholds."""
    pressure = assess_pest_pressure(plant_type, observations)
    exceeded = [p for p, flag in pressure.items() if flag]
    if not exceeded:
        return {}
    return recommend_treatments(plant_type, exceeded)


def recommend_ipm_plan(plant_type: str, observations: Mapping[str, int]) -> Dict[str, Dict[str, object]]:
    """Return integrated pest management suggestions.

    The plan includes both chemical/organic treatments and recommended
    beneficial insects for any pests exceeding action thresholds.
    """
    pressure = assess_pest_pressure(plant_type, observations)
    exceeded = [p for p, flag in pressure.items() if flag]
    if not exceeded:
        return {}

    actions = recommend_treatments(plant_type, exceeded)
    plan: Dict[str, Dict[str, object]] = {}
    for pest in exceeded:
        plan[pest] = {
            "treatment": actions.get(pest, ""),
            "beneficials": get_beneficial_insects(pest),
        }
    return plan
