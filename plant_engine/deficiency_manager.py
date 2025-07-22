"""Nutrient deficiency diagnosis utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import calculate_deficiencies
from .utils import load_dataset

DATA_FILE = "nutrient_deficiency_symptoms.json"
TREATMENT_DATA_FILE = "nutrient_deficiency_treatments.json"

# Load dataset once using cached loader
_SYMPTOMS: Dict[str, str] = load_dataset(DATA_FILE)
_TREATMENTS: Dict[str, str] = load_dataset(TREATMENT_DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_deficiency_symptom",
    "diagnose_deficiencies",
    "get_deficiency_treatment",
    "recommend_deficiency_treatments",
]


def list_known_nutrients() -> list[str]:
    """Return all nutrients with recorded deficiency symptoms."""
    return sorted(_SYMPTOMS.keys())


def get_deficiency_symptom(nutrient: str) -> str:
    """Return the symptom description for a nutrient or an empty string."""
    return _SYMPTOMS.get(nutrient, "")


def diagnose_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, str]:
    """Return deficiency symptoms based on current nutrient levels."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    return {n: get_deficiency_symptom(n) for n in deficits}


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
