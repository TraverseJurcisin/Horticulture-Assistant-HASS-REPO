from __future__ import annotations

from collections.abc import Mapping

from .utils import load_dataset

DATA_FILE = "nutrients/nutrient_volatilization_rates.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_volatilization_rate",
    "estimate_volatilization_loss",
    "compensate_for_volatilization",
]


def list_known_nutrients() -> list[str]:
    """Return nutrients with defined volatilization rates."""
    defaults = _DATA.get("default", {})
    others = [n for plant in _DATA.values() if isinstance(plant, Mapping) for n in plant]
    return sorted(set(defaults) | set(others))


def get_volatilization_rate(nutrient: str, plant_type: str | None = None) -> float:
    """Return fractional volatilization rate for ``nutrient``."""
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


def estimate_volatilization_loss(
    levels_mg: Mapping[str, float], plant_type: str | None = None
) -> dict[str, float]:
    """Return nutrient losses (mg) from volatilization."""
    losses: dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        rate = get_volatilization_rate(nutrient, plant_type)
        if rate <= 0:
            continue
        losses[nutrient] = round(float(mg) * rate, 2)
    return losses


def compensate_for_volatilization(
    levels_mg: Mapping[str, float], plant_type: str | None = None
) -> dict[str, float]:
    """Return adjusted nutrient amounts accounting for volatilization losses."""
    losses = estimate_volatilization_loss(levels_mg, plant_type)
    adjusted: dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        adjusted[nutrient] = round(float(mg) + losses.get(nutrient, 0.0), 2)
    return adjusted
