"""Disease management guideline utilities."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset, normalize_key, list_dataset_entries

RESISTANCE_FILE = "disease_resistance_ratings.json"

DATA_FILE = "disease_guidelines.json"
PREVENTION_FILE = "disease_prevention.json"
FUNGICIDE_FILE = "fungicide_recommendations.json"



# Dataset is cached by ``load_dataset`` so load once at import time
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)
_PREVENTION: Dict[str, Dict[str, str]] = load_dataset(PREVENTION_FILE)
_RESISTANCE: Dict[str, Dict[str, float]] = load_dataset(RESISTANCE_FILE)
_FUNGICIDES_RAW: Dict[str, list[str]] = load_dataset(FUNGICIDE_FILE)
_FUNGICIDES: Dict[str, list[str]] = {
    normalize_key(k): list(v) if isinstance(v, list) else []
    for k, v in _FUNGICIDES_RAW.items()
}


def list_supported_plants() -> list[str]:
    """Return all plant types with disease guidelines."""
    return list_dataset_entries(_DATA)


def get_disease_guidelines(plant_type: str) -> Dict[str, str]:
    """Return disease management guidelines for the specified plant type."""
    return _DATA.get(normalize_key(plant_type), {})


def list_known_diseases(plant_type: str) -> list[str]:
    """Return all diseases with guidelines for ``plant_type``."""
    return sorted(get_disease_guidelines(plant_type).keys())


def recommend_treatments(plant_type: str, diseases: Iterable[str]) -> Dict[str, str]:
    """Return recommended treatment strings for each observed disease."""
    guide = get_disease_guidelines(plant_type)
    actions: Dict[str, str] = {}
    for dis in diseases:
        actions[dis] = guide.get(dis, "No guideline available")
    return actions


def get_disease_prevention(plant_type: str) -> Dict[str, str]:
    """Return disease prevention guidelines for the specified plant type."""
    return _PREVENTION.get(normalize_key(plant_type), {})


def recommend_prevention(plant_type: str, diseases: Iterable[str]) -> Dict[str, str]:
    """Return recommended prevention steps for each observed disease."""
    guide = get_disease_prevention(plant_type)
    actions: Dict[str, str] = {}
    for dis in diseases:
        actions[dis] = guide.get(dis, "No guideline available")
    return actions


def get_disease_resistance(plant_type: str, disease: str) -> float | None:
    """Return relative resistance rating of a plant to ``disease``.

    Ratings are arbitrary scores (1-5). ``None`` is returned when no rating is
    defined for the plant/disease combination.
    """

    data = _RESISTANCE.get(normalize_key(plant_type), {})
    value = data.get(normalize_key(disease))
    return float(value) if isinstance(value, (int, float)) else None


def get_fungicide_options(disease: str) -> list[str]:
    """Return recommended fungicide products for ``disease``."""

    options = _FUNGICIDES.get(normalize_key(disease))
    if isinstance(options, list):
        return list(options)
    return []


def recommend_fungicides(diseases: Iterable[str]) -> Dict[str, list[str]]:
    """Return fungicide suggestions for each disease in ``diseases``."""

    recs: Dict[str, list[str]] = {}
    for dis in diseases:
        recs[dis] = get_fungicide_options(dis)
    return recs


__all__ = [
    "list_supported_plants",
    "get_disease_guidelines",
    "list_known_diseases",
    "recommend_treatments",
    "get_disease_prevention",
    "recommend_prevention",
    "get_disease_resistance",
    "get_fungicide_options",
    "recommend_fungicides",
]
