"""Estimate nutrient losses from leaching events."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

DATA_FILE = "nutrient_leaching_rates.json"

# Cache dataset on first load
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_leaching_rate",
    "estimate_leaching_loss",
    "compensate_for_leaching",
]


def list_known_nutrients() -> list[str]:
    """Return nutrients with defined leaching rates."""
    defaults = _DATA.get("default", {})
    others = [n for plant in _DATA.values() if isinstance(plant, dict) for n in plant]
    return sorted(set(defaults) | set(others))


def get_leaching_rate(nutrient: str, plant_type: str | None = None) -> float:
    """Return fractional loss rate for ``nutrient``.

    Plant-specific overrides are used when available, otherwise the
    ``default`` value from :data:`nutrient_leaching_rates.json` is returned.
    Missing values default to ``0``.
    """

    if plant_type:
        plant = _DATA.get(plant_type.lower())
        if isinstance(plant, Mapping):
            rate = plant.get(nutrient)
            if rate is not None:
                try:
                    return float(rate)
                except (TypeError, ValueError):
                    return 0.0
    try:
        return float(_DATA.get("default", {}).get(nutrient, 0.0))
    except (TypeError, ValueError):
        return 0.0


def estimate_leaching_loss(
    levels_mg: Mapping[str, float], plant_type: str | None = None
) -> Dict[str, float]:
    """Return nutrient losses (mg) from leaching."""
    losses: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        rate = get_leaching_rate(nutrient, plant_type)
        if rate <= 0:
            continue
        losses[nutrient] = round(float(mg) * rate, 2)
    return losses


def compensate_for_leaching(
    levels_mg: Mapping[str, float], plant_type: str | None = None
) -> Dict[str, float]:
    """Return adjusted nutrient amounts accounting for leaching losses."""
    losses = estimate_leaching_loss(levels_mg, plant_type)
    adjusted: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        adjusted[nutrient] = round(float(mg) + losses.get(nutrient, 0.0), 2)
    return adjusted

