"""Nutrient deficiency diagnosis utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import calculate_deficiencies
from .utils import lazy_dataset

DATA_FILE = "nutrients/nutrient_deficiency_symptoms.json"
TREATMENT_DATA_FILE = "nutrients/nutrient_deficiency_treatments.json"
MOBILITY_DATA_FILE = "nutrients/nutrient_mobility.json"
THRESHOLD_DATA_FILE = "nutrients/nutrient_deficiency_thresholds.json"
SCORE_DATA_FILE = "nutrients/deficiency_severity_scores.json"

# Load datasets lazily to avoid unnecessary work during import
_symptoms = lazy_dataset(DATA_FILE)
_treatments = lazy_dataset(TREATMENT_DATA_FILE)
_mobility = lazy_dataset(MOBILITY_DATA_FILE)
_thresholds = lazy_dataset(THRESHOLD_DATA_FILE)
_scores = lazy_dataset(SCORE_DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_deficiency_symptom",
    "diagnose_deficiencies",
    "diagnose_deficiencies_detailed",
    "get_deficiency_treatment",
    "get_nutrient_mobility",
    "classify_deficiency_levels",
    "assess_deficiency_severity",
    "calculate_deficiency_index",
    "summarize_deficiencies",
    "recommend_deficiency_treatments",
    "diagnose_deficiency_actions",
    "assess_deficiency_severity_with_synergy",
    "summarize_deficiencies_with_synergy",
    "assess_deficiency_severity_with_ph",
    "summarize_deficiencies_with_ph",
    "assess_deficiency_severity_with_ph_and_synergy",
    "summarize_deficiencies_with_ph_and_synergy",
]


def list_known_nutrients() -> list[str]:
    """Return all nutrients with recorded deficiency symptoms."""
    return sorted(_symptoms().keys())


def get_deficiency_symptom(nutrient: str) -> str:
    """Return the symptom description for a nutrient or an empty string."""
    return _symptoms().get(nutrient, "")


def get_nutrient_mobility(nutrient: str) -> str:
    """Return ``mobile`` or ``immobile`` classification for ``nutrient``."""
    return _mobility().get(nutrient, "unknown")


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
    return _treatments().get(nutrient, "")


def recommend_deficiency_treatments(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, str]:
    """Return treatments for diagnosed nutrient deficiencies."""
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    return {n: get_deficiency_treatment(n) for n in deficits}


def classify_deficiency_levels(deficits: Mapping[str, float]) -> Dict[str, str]:
    """Return severity classification for nutrient deficits."""
    levels: Dict[str, str] = {}
    for nutrient, amount in deficits.items():
        bounds = _thresholds().get(nutrient)
        if not bounds or len(bounds) != 2:
            continue
        mild, severe = bounds
        if amount < mild:
            level = "mild"
        elif amount < severe:
            level = "moderate"
        else:
            level = "severe"
        levels[nutrient] = level
    return levels


def assess_deficiency_severity(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, str]:
    """Return severity classification for each deficient nutrient."""

    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    return classify_deficiency_levels(deficits)


def diagnose_deficiency_actions(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, Dict[str, str]]:
    """Return severity and treatment recommendations for deficiencies."""

    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    if not deficits:
        return {}

    severity = classify_deficiency_levels(deficits)
    actions: Dict[str, Dict[str, str]] = {}
    for nutrient in deficits:
        actions[nutrient] = {
            "severity": severity.get(nutrient, ""),
            "treatment": get_deficiency_treatment(nutrient),
        }
    return actions


def calculate_deficiency_index(severity_map: Mapping[str, str]) -> float:
    """Return average numeric score for a deficiency severity mapping."""

    if not severity_map:
        return 0.0

    _scores.cache_clear()
    scores = _scores()
    total = 0.0
    count = 0
    for level in severity_map.values():
        try:
            total += float(scores.get(level, 0))
            count += 1
        except (TypeError, ValueError):
            continue
    return round(total / count, 2) if count else 0.0


def summarize_deficiencies(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, object]:
    """Return severity, treatments and index for current nutrient status."""

    severity = assess_deficiency_severity(current_levels, plant_type, stage)
    treatments = recommend_deficiency_treatments(
        current_levels, plant_type, stage
    )
    index = calculate_deficiency_index(severity)
    return {
        "severity": severity,
        "treatments": treatments,
        "severity_index": index,
    }


def assess_deficiency_severity_with_synergy(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, str]:
    """Return severity levels using synergy-adjusted guidelines."""

    from . import nutrient_manager

    deficits = nutrient_manager.calculate_all_deficiencies_with_synergy(
        current_levels, plant_type, stage
    )
    return classify_deficiency_levels(deficits)


def summarize_deficiencies_with_synergy(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, object]:
    """Return deficiency summary using synergy-adjusted targets."""

    from . import nutrient_manager

    severity = assess_deficiency_severity_with_synergy(
        current_levels, plant_type, stage
    )
    treatments = recommend_deficiency_treatments(
        current_levels, plant_type, stage
    )
    index = nutrient_manager.calculate_deficiency_index_with_synergy(
        current_levels, plant_type, stage
    )
    return {
        "severity": severity,
        "treatments": treatments,
        "severity_index": index,
    }


def assess_deficiency_severity_with_ph(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, str]:
    """Return severity levels using pH-adjusted guidelines."""

    from . import nutrient_manager

    deficits = nutrient_manager.calculate_all_deficiencies_with_ph(
        current_levels, plant_type, stage, ph
    )
    return classify_deficiency_levels(deficits)


def summarize_deficiencies_with_ph(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, object]:
    """Return deficiency summary using pH-adjusted targets."""

    from . import nutrient_manager

    severity = assess_deficiency_severity_with_ph(
        current_levels, plant_type, stage, ph
    )
    treatments = recommend_deficiency_treatments(
        current_levels, plant_type, stage
    )
    index = nutrient_manager.calculate_deficiency_index_with_ph(
        current_levels, plant_type, stage, ph
    )
    return {
        "severity": severity,
        "treatments": treatments,
        "severity_index": index,
    }


def assess_deficiency_severity_with_ph_and_synergy(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, str]:
    """Return severity using synergy and pH adjusted guidelines."""

    from . import nutrient_manager

    deficits = nutrient_manager.calculate_all_deficiencies_with_ph_and_synergy(
        current_levels, plant_type, stage, ph
    )
    return classify_deficiency_levels(deficits)


def summarize_deficiencies_with_ph_and_synergy(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, object]:
    """Return deficiency summary using synergy and pH adjusted targets."""

    from . import nutrient_manager

    severity = assess_deficiency_severity_with_ph_and_synergy(
        current_levels, plant_type, stage, ph
    )
    treatments = recommend_deficiency_treatments(
        current_levels, plant_type, stage
    )
    index = nutrient_manager.calculate_deficiency_index_with_ph_and_synergy(
        current_levels, plant_type, stage, ph
    )
    return {
        "severity": severity,
        "treatments": treatments,
        "severity_index": index,
    }
