"""Estimate nutrient requirements based on expected yield.

This module provides helpers for calculating total nutrient removal from
harvested biomass and the corresponding fertilizer requirements. Removal
rates are specified in :data:`nutrient_removal_rates.json` as grams of each
nutrient removed per kilogram of yield. The new
:func:`estimate_fertilizer_requirements` helper converts these requirements
into grams of fertilizer product using purity factors from
``fertilizer_purity.json``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "nutrient_removal_rates.json"

# Cached dataset loaded once at import
_RATES: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)
# Fertilizer solubility (grams per liter) loaded once at import
_SOLUBILITY: Dict[str, float] = load_dataset("fertilizer_solubility.json")

__all__ = [
    "list_supported_plants",
    "get_removal_rates",
    "estimate_total_removal",
    "estimate_required_nutrients",
    "estimate_fertilizer_requirements",
    "estimate_solution_volume",
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


def estimate_fertilizer_requirements(
    plant_type: str,
    yield_kg: float,
    fertilizers: Mapping[str, str],
    *,
    efficiency: float = 0.85,
) -> Dict[str, float]:
    """Return grams of each fertilizer needed for the expected yield.

    The calculation uses :func:`estimate_required_nutrients` to determine the
    nutrient demand and divides by product purity values loaded from
    ``fertilizer_purity.json``. Any nutrient without a matching product or
    purity factor is skipped.
    """

    required = estimate_required_nutrients(
        plant_type, yield_kg, efficiency=efficiency
    ).nutrients_g

    purity_data = load_dataset("fertilizer_purity.json")

    totals: Dict[str, float] = {}
    for nutrient, grams in required.items():
        fert_id = fertilizers.get(nutrient)
        if not fert_id:
            continue
        purity_info = purity_data.get(fert_id)
        if not isinstance(purity_info, Mapping):
            continue
        purity = purity_info.get(nutrient)
        try:
            purity_val = float(purity)
        except (TypeError, ValueError):
            continue
        if purity_val <= 0:
            continue
        totals[fert_id] = round(totals.get(fert_id, 0.0) + grams / purity_val, 2)

    return totals


def estimate_solution_volume(masses: Mapping[str, float]) -> Dict[str, float]:
    """Return liters of water needed to dissolve each fertilizer mass.

    Solubility limits from ``fertilizer_solubility.json`` are used to
    convert grams of product into the minimum volume of water required.
    Unknown fertilizers are ignored.
    """

    volumes: Dict[str, float] = {}
    for fert_id, grams in masses.items():
        if grams <= 0:
            continue
        sol = _SOLUBILITY.get(fert_id)
        try:
            sol_rate = float(sol)
        except (TypeError, ValueError):
            continue
        if sol_rate <= 0:
            continue
        volumes[fert_id] = round(grams / sol_rate, 3)

    return volumes
