"""Sap nutrient analysis utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key

DATA_FILE = "sap_analysis_targets.json"
WEIGHT_FILE = "sap_analysis_score_weights.json"

_TARGETS: Dict[str, Dict[str, Dict[str, list[float]]]] = load_dataset(DATA_FILE)
_WEIGHTS: Dict[str, float] = load_dataset(WEIGHT_FILE)

__all__ = [
    "get_sap_targets",
    "evaluate_sap_levels",
    "score_sap_levels",
]


def get_sap_targets(plant_type: str, stage: str) -> Dict[str, list[float]]:
    """Return recommended sap nutrient ranges for a plant stage."""
    return _TARGETS.get(normalize_key(plant_type), {}).get(normalize_key(stage), {})


def evaluate_sap_levels(
    plant_type: str,
    stage: str,
    sample_levels: Mapping[str, float],
) -> Dict[str, str]:
    """Classify sap nutrient levels as 'low', 'ok' or 'high'."""
    targets = get_sap_targets(plant_type, stage)
    results: Dict[str, str] = {}
    for nutrient, value in sample_levels.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        bounds = targets.get(nutrient)
        if bounds and len(bounds) == 2:
            low, high = bounds
            if val < low:
                results[nutrient] = "low"
            elif val > high:
                results[nutrient] = "high"
            else:
                results[nutrient] = "ok"
    return results


def score_sap_levels(
    plant_type: str,
    stage: str,
    sample_levels: Mapping[str, float],
    *,
    weights: Mapping[str, float] | None = None,
) -> float:
    """Return a 0-100 score for how close ``sample_levels`` are to targets."""
    ranges = get_sap_targets(plant_type, stage)
    if not ranges:
        return 0.0
    if weights is None:
        weights = _WEIGHTS

    total = 0.0
    total_weight = 0.0
    for nutrient, bounds in ranges.items():
        if (
            not isinstance(bounds, (list, tuple))
            or len(bounds) != 2
            or nutrient not in sample_levels
        ):
            continue
        try:
            val = float(sample_levels[nutrient])
            low, high = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            continue
        weight = float(weights.get(nutrient, 1.0))
        if val < low:
            ratio = max(val, 0) / low if low > 0 else 0.0
        elif val > high:
            ratio = high / val if val > 0 else 0.0
        else:
            ratio = 1.0
        total += ratio * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round((total / total_weight) * 100, 1)
