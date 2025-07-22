from __future__ import annotations

"""Pest monitoring utilities using threshold datasets."""

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key
from .pest_manager import recommend_treatments

DATA_FILE = "pest_thresholds.json"

# Load once with caching
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_pest_thresholds",
    "assess_pest_pressure",
    "recommend_threshold_actions",
]


def get_pest_thresholds(plant_type: str) -> Dict[str, int]:
    """Return pest count thresholds for ``plant_type``.

    Lookup is case-insensitive and spaces are ignored so ``"Citrus"`` and
    ``"citrus"`` map to the same dataset entry.
    """

    return _THRESHOLDS.get(normalize_key(plant_type), {})


def list_supported_plants() -> list[str]:
    """Return plant types with pest threshold definitions."""

    return sorted(_THRESHOLDS.keys())


def assess_pest_pressure(plant_type: str, observations: Mapping[str, int]) -> Dict[str, bool]:
    """Return mapping of pests to ``True`` if threshold exceeded."""

    thresholds = get_pest_thresholds(plant_type)
    pressure: Dict[str, bool] = {}
    for pest, count in observations.items():
        key = normalize_key(pest)
        thresh = thresholds.get(key)
        if thresh is None:
            continue
        pressure[key] = count >= thresh
    return pressure


def recommend_threshold_actions(plant_type: str, observations: Mapping[str, int]) -> Dict[str, str]:
    """Return treatment actions for pests exceeding thresholds."""

    pressure = assess_pest_pressure(plant_type, observations)
    exceeded = [p for p, flag in pressure.items() if flag]
    if not exceeded:
        return {}
    return recommend_treatments(plant_type, exceeded)
