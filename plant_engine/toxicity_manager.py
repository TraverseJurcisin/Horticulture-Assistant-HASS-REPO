"""Nutrient toxicity management utilities.

This module exposes helper functions for checking nutrient levels against
toxicity thresholds and suggesting mitigation actions.  Datasets of toxicity
symptoms and treatments are loaded at import time for fast access.
"""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_toxicity_thresholds.json"
SYMPTOMS_FILE = "nutrient_toxicity_symptoms.json"
TREATMENTS_FILE = "nutrient_toxicity_treatments.json"

# Loaded once using cached loader
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)
_SYMPTOMS: Dict[str, str] = load_dataset(SYMPTOMS_FILE)
_TREATMENTS: Dict[str, str] = load_dataset(TREATMENTS_FILE)

__all__ = [
    "list_supported_plants",
    "get_toxicity_thresholds",
    "check_toxicities",
    "list_known_nutrients",
    "get_toxicity_symptom",
    "diagnose_toxicities",
    "get_toxicity_treatment",
    "recommend_toxicity_treatments",
    "calculate_toxicity_index",
]


def list_supported_plants() -> list[str]:
    """Return plant types with specific toxicity data."""
    return sorted(k for k in _DATA.keys() if k != "default")


def get_toxicity_thresholds(plant_type: str) -> Dict[str, float]:
    """Return toxicity thresholds for ``plant_type`` or defaults."""
    plant = _DATA.get(normalize_key(plant_type))
    if plant is None:
        plant = _DATA.get("default", {})
    return plant if isinstance(plant, dict) else {}


def check_toxicities(current_levels: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return nutrient amounts exceeding toxicity thresholds."""
    thresholds = get_toxicity_thresholds(plant_type)
    toxic: Dict[str, float] = {}
    for nutrient, limit in thresholds.items():
        try:
            level = float(current_levels.get(nutrient, 0))
            excess = level - float(limit)
        except (TypeError, ValueError):
            continue
        if excess > 0:
            toxic[nutrient] = round(excess, 2)
    return toxic


def list_known_nutrients() -> list[str]:
    """Return nutrients with recorded toxicity symptoms."""
    return sorted(_SYMPTOMS.keys())


def get_toxicity_symptom(nutrient: str) -> str:
    """Return the symptom description for ``nutrient`` or an empty string."""
    return _SYMPTOMS.get(nutrient, "")


def diagnose_toxicities(
    current_levels: Mapping[str, float], plant_type: str
) -> Dict[str, str]:
    """Return toxicity symptoms for nutrients exceeding thresholds."""
    excess = check_toxicities(current_levels, plant_type)
    return {n: get_toxicity_symptom(n) for n in excess}


def get_toxicity_treatment(nutrient: str) -> str:
    """Return recommended mitigation for a nutrient toxicity."""
    return _TREATMENTS.get(nutrient, "")


def recommend_toxicity_treatments(
    current_levels: Mapping[str, float], plant_type: str
) -> Dict[str, str]:
    """Return treatments for diagnosed nutrient toxicities."""
    excess = check_toxicities(current_levels, plant_type)
    return {n: get_toxicity_treatment(n) for n in excess}


def calculate_toxicity_index(
    current_levels: Mapping[str, float], plant_type: str
) -> float:
    """Return weighted toxicity index for current nutrient levels.

    The index is 0 when all nutrients are within safe limits and increases
    proportionally to how far levels exceed their toxicity thresholds.
    Nutrient weights from :data:`nutrient_weights.json` are applied so
    more important elements contribute more to the score.
    """

    thresholds = get_toxicity_thresholds(plant_type)
    if not thresholds:
        return 0.0

    from .utils import clear_dataset_cache, load_dataset

    # Reload weights to honor any environment changes that may have occurred
    clear_dataset_cache()
    weights: Mapping[str, float] = load_dataset("nutrient_weights.json") or {}

    total_weight = 0.0
    score = 0.0
    for nutrient, limit in thresholds.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        if current <= limit:
            continue
        ratio = (current - limit) / limit
        try:
            weight = float(weights.get(nutrient, 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        score += weight * ratio
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round((score / total_weight) * 100, 1)
