"""Estimate nutrient requirements based on expected yield.

This module provides helpers for calculating total nutrient removal from
harvested biomass and the corresponding fertilizer requirements. Removal
rates are specified in :data:`nutrient_removal_rates.json` as grams of each
nutrient removed per kilogram of yield.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "nutrient_removal_rates.json"

# Cached dataset loaded once at import
_RATES: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_removal_rates",
    "estimate_total_removal",
    "estimate_required_nutrients",
    "RemovalEstimate",
]


@dataclass(frozen=True)
class RemovalEstimate:
    """Container for nutrient removal calculations."""

    nutrients_g: Dict[str, float]

    def as_dict(self) -> Dict[str, Dict[str, float]]:
        return {"nutrients_g": dict(self.nutrients_g)}


def list_supported_plants() -> list[str]:
    """Return plant types with removal rate data."""
    return list_dataset_entries(_RATES)


def get_removal_rates(plant_type: str) -> Dict[str, float]:
    """Return per-kg nutrient removal rates for ``plant_type``."""
    raw = _RATES.get(normalize_key(plant_type), {})
    rates: Dict[str, float] = {}
    for n, val in raw.items():
        try:
            rates[n] = float(val)
        except (TypeError, ValueError):
            continue
    return rates


def estimate_total_removal(plant_type: str, yield_kg: float) -> RemovalEstimate:
    """Return total nutrient removal for the given yield."""
    if yield_kg <= 0:
        return RemovalEstimate({})
    rates = get_removal_rates(plant_type)
    totals = {n: round(rate * yield_kg, 2) for n, rate in rates.items()}
    return RemovalEstimate(totals)


def estimate_required_nutrients(
    plant_type: str,
    yield_kg: float,
    *,
    efficiency: float = 0.85,
) -> RemovalEstimate:
    """Return fertilizer amounts required accounting for efficiency losses."""
    if efficiency <= 0:
        raise ValueError("efficiency must be > 0")
    removal = estimate_total_removal(plant_type, yield_kg).nutrients_g
    required = {n: round(val / efficiency, 2) for n, val in removal.items()}
    return RemovalEstimate(required)
