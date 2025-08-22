from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

DATA_FILE = "nutrients/nutrient_runoff_rates.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_runoff_rate",
    "estimate_runoff_loss",
    "compensate_for_runoff",
    "estimate_cumulative_runoff_loss",
    "project_levels_after_runoff",
]


def list_known_nutrients() -> list[str]:
    """Return nutrients with defined runoff rates."""
    defaults = _DATA.get("default", {})
    others = [n for plant in _DATA.values() if isinstance(plant, Mapping) for n in plant]
    return sorted(set(defaults) | set(others))


def get_runoff_rate(nutrient: str, plant_type: str | None = None) -> float:
    """Return fractional runoff rate for ``nutrient``."""
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


def estimate_runoff_loss(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return nutrient losses (mg) from runoff."""
    losses: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        rate = get_runoff_rate(nutrient, plant_type)
        if rate <= 0:
            continue
        losses[nutrient] = round(float(mg) * rate, 2)
    return losses


def compensate_for_runoff(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return adjusted nutrient amounts accounting for runoff losses."""
    losses = estimate_runoff_loss(levels_mg, plant_type)
    adjusted: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        adjusted[nutrient] = round(float(mg) + losses.get(nutrient, 0.0), 2)
    return adjusted


def estimate_cumulative_runoff_loss(levels_mg: Mapping[str, float], plant_type: str | None, cycles: int) -> Dict[str, float]:
    """Return nutrient losses after multiple runoff ``cycles``."""
    if cycles <= 0:
        raise ValueError("cycles must be positive")

    losses: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        rate = get_runoff_rate(nutrient, plant_type)
        if rate <= 0:
            continue
        fraction = 1 - (1 - rate) ** cycles
        losses[nutrient] = round(float(mg) * fraction, 2)
    return losses


def project_levels_after_runoff(levels_mg: Mapping[str, float], plant_type: str | None, cycles: int) -> Dict[str, float]:
    """Return remaining nutrient levels after repeated runoff."""
    losses = estimate_cumulative_runoff_loss(levels_mg, plant_type, cycles)
    remaining: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        remaining[nutrient] = round(float(mg) - losses.get(nutrient, 0.0), 2)
    return remaining
