"""Nutrient deficiency diagnosis utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import calculate_deficiencies
from .utils import load_dataset

DATA_FILE = "nutrient_deficiency_symptoms.json"
TREATMENT_DATA_FILE = "nutrient_deficiency_treatments.json"
MOBILITY_DATA_FILE = "nutrient_mobility.json"

# Load dataset once using cached loader
_SYMPTOMS: Dict[str, str] = load_dataset(DATA_FILE)
_TREATMENTS: Dict[str, str] = load_dataset(TREATMENT_DATA_FILE)
_MOBILITY: Dict[str, str] = load_dataset(MOBILITY_DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_deficiency_symptom",
    "diagnose_deficiencies",
    "diagnose_deficiencies_detailed",
    "get_deficiency_treatment",
    "get_nutrient_mobility",
    "recommend_deficiency_treatments",
]


def list_known_nutrients() -> list[str]:
    """Return all nutrients with recorded deficiency symptoms."""
    return sorted(_SYMPTOMS.keys())


def get_deficiency_symptom(nutrient: str) -> str:
    """Return the symptom description for a nutrient or an empty string."""
    return _SYMPTOMS.get(nutrient, "")


def get_nutrient_mobility(nutrient: str) -> str:
    """Return ``mobile`` or ``immobile`` classification for ``nutrient``."""
    return _MOBILITY.get(nutrient, "unknown")


def diagnose_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, str]:
    """Return deficiency symptoms based on current nutrient levels."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    return {n: get_deficiency_symptom(n) for n in deficits}


def diagnose_deficiencies_detailed(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, Dict[str, str]]:
    """Return symptoms and mobility for each deficient nutrient."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    result: Dict[str, Dict[str, str]] = {}
    for nutrient in deficits:
        result[nutrient] = {
            "symptom": get_deficiency_symptom(nutrient),
            "mobility": get_nutrient_mobility(nutrient),
        }
    return result


def get_deficiency_treatment(nutrient: str) -> str:
    """Return suggested treatment for a nutrient deficiency."""
    return _TREATMENTS.get(nutrient, "")


def recommend_deficiency_treatments(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, str]:
    """Return treatments for diagnosed nutrient deficiencies."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    return {n: get_deficiency_treatment(n) for n in deficits}
