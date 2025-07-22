"""Helpers for calculating nutrients from fertilizer products."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict

from plant_engine.utils import load_dataset

DATA_FILE = "fertilizers/fertilizer_products.json"
PRICE_FILE = "fertilizers/fertilizer_prices.json"


@dataclass(frozen=True)
class Fertilizer:
    """Fertilizer product information."""

    density_kg_per_l: float
    guaranteed_analysis: Dict[str, float]
    product_name: str | None = None
    wsda_product_number: str | None = None


@lru_cache(maxsize=None)
def _inventory() -> Dict[str, Fertilizer]:
    """Return fertilizer inventory loaded from :mod:`data`."""
    data = load_dataset(DATA_FILE)
    inventory: Dict[str, Fertilizer] = {}
    for name, info in data.items():
        inventory[name] = Fertilizer(
            density_kg_per_l=info.get("density_kg_per_l", 1.0),
            guaranteed_analysis=info.get("guaranteed_analysis", {}),
            product_name=info.get("product_name"),
            wsda_product_number=info.get("wsda_product_number"),
        )
    return inventory


@lru_cache(maxsize=None)
def _price_map() -> Dict[str, float]:
    """Return fertilizer prices loaded from :mod:`data`."""
    return load_dataset(PRICE_FILE)


MOLAR_MASS_CONVERSIONS = {
    "P2O5": ("P", 0.436),
    "K2O": ("K", 0.830),
}


def convert_guaranteed_analysis(ga: dict) -> dict:
    """Return GA with P₂O₅/K₂O converted to elemental P and K."""
    result: dict[str, float] = {}
    for k, v in ga.items():
        if k in MOLAR_MASS_CONVERSIONS:
            element, factor = MOLAR_MASS_CONVERSIONS[k]
            result[element] = result.get(element, 0) + v * factor
        else:
            result[k] = result.get(k, 0) + v
    return result


def calculate_fertilizer_nutrients(
    plant_id: str, fertilizer_id: str, volume_ml: float
) -> Dict[str, object]:
    """Return nutrient mass (mg) for ``volume_ml`` of a fertilizer."""
    if volume_ml <= 0:
        raise ValueError("volume_ml must be positive")

    inventory = _inventory()
    if fertilizer_id not in inventory:
        raise ValueError(f"Fertilizer '{fertilizer_id}' not found in inventory.")

    fert = inventory[fertilizer_id]
    density = fert.density_kg_per_l
    ga = convert_guaranteed_analysis(fert.guaranteed_analysis)

    volume_l = volume_ml / 1000
    weight_kg = volume_l * density
    weight_g = weight_kg * 1000

    output = {}
    for element, pct in ga.items():
        nutrient_mass_mg = weight_g * pct * 1000
        output[element] = round(nutrient_mass_mg, 2)

    return {
        "plant_id": plant_id,
        "fertilizer_id": fertilizer_id,
        "volume_ml": volume_ml,
        "datetime": datetime.datetime.now().isoformat(),
        "nutrients": output,
    }


def calculate_fertilizer_cost(fertilizer_id: str, volume_ml: float) -> float:
    """Return estimated cost for ``volume_ml`` of fertilizer.

    The price data is stored in :data:`PRICE_FILE` as USD per liter.
    A ``KeyError`` is raised if the product price is unavailable.
    """

    if volume_ml <= 0:
        raise ValueError("volume_ml must be positive")

    prices = _price_map()
    if fertilizer_id not in prices:
        raise KeyError(f"Price for '{fertilizer_id}' is not defined")

    cost = prices[fertilizer_id] * (volume_ml / 1000)
    return round(cost, 2)


def estimate_mix_cost(schedule: Mapping[str, float]) -> float:
    """Return estimated USD cost for a fertilizer mix.

    ``schedule`` maps fertilizer identifiers to grams of product. Prices are
    stored in :data:`PRICE_FILE` as USD per liter and densities are read from
    :data:`DATA_FILE` to convert grams to liters. A ``KeyError`` is raised if
    any product lacks price or density information.
    """

    prices = _price_map()
    inventory = _inventory()

    total = 0.0
    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        if fert_id not in prices:
            raise KeyError(f"Price for '{fert_id}' is not defined")
        if fert_id not in inventory:
            raise KeyError(f"Density for '{fert_id}' is not defined")

        density = inventory[fert_id].density_kg_per_l  # kg/L
        grams_per_liter = density * 1000
        volume_l = grams / grams_per_liter
        total += prices[fert_id] * volume_l

    return round(total, 2)


__all__ = [
    "calculate_fertilizer_nutrients",
    "convert_guaranteed_analysis",
    "calculate_fertilizer_cost",
    "estimate_mix_cost",
    "list_products",
    "get_product_info",
]


def list_products() -> list[str]:
    """Return available fertilizer product identifiers."""
    return sorted(_inventory().keys())


def get_product_info(fertilizer_id: str) -> Fertilizer:
    """Return :class:`Fertilizer` details for ``fertilizer_id``."""
    inv = _inventory()
    if fertilizer_id not in inv:
        raise KeyError(f"Unknown fertilizer '{fertilizer_id}'")
    return inv[fertilizer_id]
