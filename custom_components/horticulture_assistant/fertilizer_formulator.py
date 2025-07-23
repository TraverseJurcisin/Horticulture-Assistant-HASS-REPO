"""Fertilizer formulation helpers.

This module provides utilities for converting guaranteed analysis values,
estimating nutrient masses, computing mix concentrations and costs.  The new
``estimate_cost_per_nutrient`` helper exposes the cost efficiency of a product
for each nutrient based on the inventory and price datasets.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Mapping

from plant_engine.utils import load_dataset

DATA_FILE = "fertilizers/fertilizer_products.json"
PRICE_FILE = "fertilizers/fertilizer_prices.json"
SOLUBILITY_FILE = "fertilizer_solubility.json"


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


@lru_cache(maxsize=None)
def _solubility_map() -> Dict[str, float]:
    """Return maximum solubility (g/L) for each fertilizer."""
    return load_dataset(SOLUBILITY_FILE)


MOLAR_MASS_CONVERSIONS = {
    "P2O5": ("P", 0.436),
    "K2O": ("K", 0.830),
}


def convert_guaranteed_analysis(ga: dict) -> dict:
    """Return GA with P₂O₅/K₂O converted to elemental P and K."""
    result: dict[str, float] = {}
    for k, v in ga.items():
        if v is None:
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if k in MOLAR_MASS_CONVERSIONS:
            element, factor = MOLAR_MASS_CONVERSIONS[k]
            result[element] = result.get(element, 0) + val * factor
        else:
            result[k] = result.get(k, 0) + val
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


def calculate_fertilizer_nutrients_from_mass(
    fertilizer_id: str, grams: float
) -> Dict[str, float]:
    """Return nutrient mass (mg) for ``grams`` of fertilizer product."""

    if grams <= 0:
        raise ValueError("grams must be positive")

    inventory = _inventory()
    if fertilizer_id not in inventory:
        raise ValueError(f"Fertilizer '{fertilizer_id}' not found in inventory.")

    ga = convert_guaranteed_analysis(inventory[fertilizer_id].guaranteed_analysis)
    return {element: round(grams * pct * 1000, 2) for element, pct in ga.items()}


def calculate_fertilizer_ppm(
    fertilizer_id: str, grams: float, volume_l: float
) -> Dict[str, float]:
    """Return nutrient ppm for ``grams`` dissolved in ``volume_l`` solution."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    nutrients = calculate_fertilizer_nutrients_from_mass(fertilizer_id, grams)
    return {n: round(mg / volume_l, 2) for n, mg in nutrients.items()}


def calculate_mass_for_target_ppm(
    fertilizer_id: str,
    nutrient: str,
    target_ppm: float,
    volume_l: float,
) -> float:
    """Return grams of ``fertilizer_id`` required for ``target_ppm`` of ``nutrient``.

    Parameters
    ----------
    fertilizer_id : str
        Inventory identifier for the fertilizer product.
    nutrient : str
        Nutrient code present in the product guaranteed analysis.
    target_ppm : float
        Desired concentration in parts per million.
    volume_l : float
        Final solution volume in liters.

    Returns
    -------
    float
        Grams of fertilizer product needed.

    Raises
    ------
    KeyError
        If ``fertilizer_id`` or ``nutrient`` is not found.
    ValueError
        If ``target_ppm`` or ``volume_l`` is not positive.
    """

    if target_ppm <= 0:
        raise ValueError("target_ppm must be positive")
    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    inventory = _inventory()
    if fertilizer_id not in inventory:
        raise KeyError(f"Fertilizer '{fertilizer_id}' not found in inventory.")

    ga = convert_guaranteed_analysis(inventory[fertilizer_id].guaranteed_analysis)
    if nutrient not in ga or ga[nutrient] <= 0:
        raise KeyError(f"Nutrient '{nutrient}' not found in guaranteed analysis")

    fraction = ga[nutrient]
    grams = (target_ppm * volume_l) / (fraction * 1000)
    return round(grams, 3)


def calculate_fertilizer_cost_from_mass(fertilizer_id: str, grams: float) -> float:
    """Return estimated cost for ``grams`` of fertilizer product."""

    if grams <= 0:
        raise ValueError("grams must be positive")

    prices = _price_map()
    inventory = _inventory()

    if fertilizer_id not in prices:
        raise KeyError(f"Price for '{fertilizer_id}' is not defined")
    if fertilizer_id not in inventory:
        raise KeyError(f"Density for '{fertilizer_id}' is not defined")

    density = inventory[fertilizer_id].density_kg_per_l
    volume_l = grams / (density * 1000)
    return round(prices[fertilizer_id] * volume_l, 2)


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


def estimate_mix_cost_per_plant(schedule: Mapping[str, float], num_plants: int) -> float:
    """Return cost per plant for ``schedule`` applied to ``num_plants``.

    ``num_plants`` must be positive. Costs are estimated using
    :func:`estimate_mix_cost` and divided by the number of plants.
    """

    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

    total_cost = estimate_mix_cost(schedule)
    return round(total_cost / num_plants, 4)


def estimate_cost_breakdown(schedule: Mapping[str, float]) -> Dict[str, float]:
    """Return estimated cost contribution per nutrient in ``schedule``.

    Each entry in ``schedule`` maps a fertilizer ID to the grams of product
    used. Prices and densities are loaded from the built-in datasets and the
    guaranteed analysis is used to apportion the cost of each fertilizer across
    its nutrients. The returned mapping contains nutrient codes with dollar
    amounts rounded to two decimals.
    """

    prices = _price_map()
    inventory = _inventory()

    breakdown: Dict[str, float] = {}
    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        if fert_id not in prices:
            raise KeyError(f"Price for '{fert_id}' is not defined")
        if fert_id not in inventory:
            raise KeyError(f"Density for '{fert_id}' is not defined")

        density = inventory[fert_id].density_kg_per_l
        grams_per_liter = density * 1000
        volume_l = grams / grams_per_liter
        cost = prices[fert_id] * volume_l

        ga = convert_guaranteed_analysis(inventory[fert_id].guaranteed_analysis)
        total_pct = sum(ga.values())
        if total_pct <= 0:
            continue

        for nutrient, pct in ga.items():
            share = cost * (pct / total_pct)
            breakdown[nutrient] = round(breakdown.get(nutrient, 0.0) + share, 2)

    return breakdown


def calculate_mix_nutrients(schedule: Mapping[str, float]) -> Dict[str, float]:
    """Return nutrient totals (mg) for a fertilizer mix."""

    inventory = _inventory()
    totals: Dict[str, float] = {}

    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        if fert_id not in inventory:
            raise KeyError(f"Unknown fertilizer '{fert_id}'")

        ga = convert_guaranteed_analysis(
            inventory[fert_id].guaranteed_analysis
        )
        for nutrient, pct in ga.items():
            totals[nutrient] = round(
                totals.get(nutrient, 0.0) + grams * pct * 1000, 2
            )

    return totals


def calculate_mix_ppm(schedule: Mapping[str, float], volume_l: float) -> Dict[str, float]:
    """Return nutrient concentration (ppm) for ``schedule`` dissolved in ``volume_l``.

    ``volume_l`` is the final solution volume in liters. The returned mapping
    contains nutrient codes mapped to parts per million. A ``ValueError`` is
    raised if ``volume_l`` is not positive.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    totals = calculate_mix_nutrients(schedule)
    return {nutrient: round(mg / volume_l, 2) for nutrient, mg in totals.items()}


def calculate_mix_density(schedule: Mapping[str, float]) -> float:
    """Return approximate density (kg/L) of a fertilizer mix.

    The ``schedule`` mapping specifies grams of each fertilizer product. Densities
    are looked up in the inventory dataset. The density is computed as the total
    mass divided by the total volume of all products. An empty schedule results in
    ``0.0``.
    """

    inventory = _inventory()
    total_mass_kg = 0.0
    total_volume_l = 0.0

    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        if fert_id not in inventory:
            raise KeyError(f"Unknown fertilizer '{fert_id}'")

        density = inventory[fert_id].density_kg_per_l
        if density is None:
            raise KeyError(f"Density for '{fert_id}' is not defined")

        mass_kg = grams / 1000
        volume_l = mass_kg / density
        total_mass_kg += mass_kg
        total_volume_l += volume_l

    if total_volume_l == 0:
        return 0.0

    return round(total_mass_kg / total_volume_l, 3)


def estimate_solution_mass(schedule: Mapping[str, float], volume_l: float) -> float:
    """Return total solution mass (kg) for ``schedule`` dissolved in ``volume_l``.

    The calculation assumes water density is 1 kg/L and simply adds the mass
    of all fertilizer products. A ``ValueError`` is raised when ``volume_l`` is
    negative.
    """

    if volume_l < 0:
        raise ValueError("volume_l must be non-negative")

    fertilizer_mass_kg = sum(max(g, 0.0) for g in schedule.values()) / 1000
    return round(volume_l + fertilizer_mass_kg, 3)


def check_solubility_limits(schedule: Mapping[str, float], volume_l: float) -> Dict[str, float]:
    """Return grams per liter exceeding solubility limits.

    Parameters
    ----------
    schedule : Mapping[str, float]
        Mapping of fertilizer IDs to grams of product.
    volume_l : float
        Total solution volume in liters.

    Returns
    -------
    Dict[str, float]
        Mapping of fertilizer IDs to grams per liter over the limit. Unknown
        fertilizers are ignored. A ``ValueError`` is raised if ``volume_l`` is
        not positive.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    limits = _solubility_map()
    warnings: Dict[str, float] = {}
    for fert_id, grams in schedule.items():
        max_g_l = limits.get(fert_id)
        if max_g_l is None:
            continue
        grams_per_l = grams / volume_l
        if grams_per_l > max_g_l:
            warnings[fert_id] = round(grams_per_l - max_g_l, 2)
    return warnings


def estimate_cost_per_nutrient(fertilizer_id: str) -> Dict[str, float]:
    """Return cost per gram of each nutrient in a fertilizer product."""

    inventory = _inventory()
    prices = _price_map()

    if fertilizer_id not in inventory:
        raise KeyError(f"Fertilizer '{fertilizer_id}' not found in inventory.")
    if fertilizer_id not in prices:
        raise KeyError(f"Price for '{fertilizer_id}' is not defined")

    info = inventory[fertilizer_id]
    density = info.density_kg_per_l
    if density <= 0:
        raise ValueError("density must be positive")

    cost_per_gram = prices[fertilizer_id] / (density * 1000)
    ga = convert_guaranteed_analysis(info.guaranteed_analysis)

    costs: Dict[str, float] = {}
    for nutrient, fraction in ga.items():
        if fraction <= 0:
            continue
        costs[nutrient] = round(cost_per_gram / fraction, 4)

    return costs


__all__ = [
    "calculate_fertilizer_nutrients",
    "calculate_fertilizer_nutrients_from_mass",
    "convert_guaranteed_analysis",
    "calculate_fertilizer_cost",
    "calculate_fertilizer_cost_from_mass",
    "calculate_fertilizer_ppm",
    "estimate_mix_cost",
    "estimate_mix_cost_per_plant",
    "estimate_cost_breakdown",
    "calculate_mix_nutrients",
    "calculate_mix_density",
    "estimate_solution_mass",
    "check_solubility_limits",
    "estimate_cost_per_nutrient",
    "calculate_mass_for_target_ppm",
    "list_products",
    "get_product_info",
    "find_products",
    "calculate_mix_ppm",
]


def list_products() -> list[str]:
    """Return available fertilizer product identifiers sorted by name."""
    inv = _inventory()
    return sorted(inv.keys(), key=lambda pid: inv[pid].product_name or pid)


def get_product_info(fertilizer_id: str) -> Fertilizer:
    """Return :class:`Fertilizer` details for ``fertilizer_id``."""
    inv = _inventory()
    if fertilizer_id not in inv:
        raise KeyError(f"Unknown fertilizer '{fertilizer_id}'")
    return inv[fertilizer_id]


def find_products(term: str) -> list[str]:
    """Return product IDs matching ``term`` in the ID or product name."""
    if not term:
        return []
    term = term.lower()
    results: list[str] = []
    for pid, info in _inventory().items():
        name = (info.product_name or "").lower()
        if term in pid.lower() or term in name:
            results.append(pid)
    return sorted(results)

