"""Disease management guideline utilities."""

from __future__ import annotations

from collections.abc import Iterable

from .utils import list_dataset_entries, load_dataset, normalize_key

RESISTANCE_FILE = "diseases/disease_resistance_ratings.json"

DATA_FILE = "diseases/disease_guidelines.json"
PREVENTION_FILE = "diseases/disease_prevention.json"
FUNGICIDE_FILE = "fungicides/fungicide_recommendations.json"
RATE_FILE = "fungicides/fungicide_application_rates.json"


# Dataset is cached by ``load_dataset`` so load once at import time
_DATA: dict[str, dict[str, str]] = load_dataset(DATA_FILE)
_PREVENTION: dict[str, dict[str, str]] = load_dataset(PREVENTION_FILE)
_RESISTANCE: dict[str, dict[str, float]] = load_dataset(RESISTANCE_FILE)
_FUNGICIDES_RAW: dict[str, list[str]] = load_dataset(FUNGICIDE_FILE)
_RATES_RAW: dict[str, float] = load_dataset(RATE_FILE)
_FUNGICIDES: dict[str, list[str]] = {
    normalize_key(k): list(v) if isinstance(v, list) else [] for k, v in _FUNGICIDES_RAW.items()
}
_RATES: dict[str, float] = {
    normalize_key(k): float(v) for k, v in _RATES_RAW.items() if isinstance(v, int | float)
}


def list_supported_plants() -> list[str]:
    """Return all plant types with disease guidelines."""
    return list_dataset_entries(_DATA)


def get_disease_guidelines(plant_type: str) -> dict[str, str]:
    """Return disease management guidelines for the specified plant type."""
    return _DATA.get(normalize_key(plant_type), {})


def list_known_diseases(plant_type: str) -> list[str]:
    """Return all diseases with guidelines for ``plant_type``."""
    return sorted(get_disease_guidelines(plant_type).keys())


def recommend_treatments(plant_type: str, diseases: Iterable[str]) -> dict[str, str]:
    """Return recommended treatment strings for each observed disease."""
    guide = get_disease_guidelines(plant_type)
    actions: dict[str, str] = {}
    for dis in diseases:
        actions[dis] = guide.get(dis, "No guideline available")
    return actions


def get_disease_prevention(plant_type: str) -> dict[str, str]:
    """Return disease prevention guidelines for the specified plant type."""
    return _PREVENTION.get(normalize_key(plant_type), {})


def recommend_prevention(plant_type: str, diseases: Iterable[str]) -> dict[str, str]:
    """Return recommended prevention steps for each observed disease."""
    guide = get_disease_prevention(plant_type)
    actions: dict[str, str] = {}
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
    return float(value) if isinstance(value, int | float) else None


def get_fungicide_options(disease: str) -> list[str]:
    """Return recommended fungicide products for ``disease``."""

    options = _FUNGICIDES.get(normalize_key(disease))
    if isinstance(options, list):
        return list(options)
    return []


def get_fungicide_application_rate(product: str) -> float | None:
    """Return recommended application rate for a fungicide product."""

    value = _RATES.get(normalize_key(product))
    return float(value) if isinstance(value, int | float) else None


def calculate_fungicide_mix(disease: str, volume_l: float) -> dict[str, float]:
    """Return fungicide grams for treating ``volume_l`` solution."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    mix: dict[str, float] = {}
    for product in get_fungicide_options(disease):
        rate = get_fungicide_application_rate(product)
        if rate is None:
            continue
        mix[product] = round(rate * volume_l, 2)
    return mix


def recommend_fungicides(diseases: Iterable[str]) -> dict[str, list[str]]:
    """Return fungicide suggestions for each disease in ``diseases``."""

    recs: dict[str, list[str]] = {}
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
    "get_fungicide_application_rate",
    "calculate_fungicide_mix",
    "recommend_fungicides",
]
