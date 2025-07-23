"""Leaf tissue analysis helpers."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key

DATA_FILE = "leaf_tissue_targets.json"
_TARGETS: Dict[str, Dict[str, Dict[str, list[float]]]] = load_dataset(DATA_FILE)

__all__ = ["get_target_ranges", "evaluate_tissue_levels"]


def get_target_ranges(plant_type: str, stage: str) -> Dict[str, list[float]]:
    """Return optimal nutrient ranges for ``plant_type`` at ``stage``."""
    return _TARGETS.get(normalize_key(plant_type), {}).get(normalize_key(stage), {})


def evaluate_tissue_levels(
    plant_type: str,
    stage: str,
    sample_levels: Mapping[str, float],
) -> Dict[str, str]:
    """Classify tissue nutrient levels as 'low', 'ok', or 'high'."""
    targets = get_target_ranges(plant_type, stage)
    results: Dict[str, str] = {}
    for nutrient, value in sample_levels.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        low_high = targets.get(nutrient)
        if low_high and len(low_high) == 2:
            low, high = low_high
            if val < low:
                results[nutrient] = "low"
            elif val > high:
                results[nutrient] = "high"
            else:
                results[nutrient] = "ok"
    return results
