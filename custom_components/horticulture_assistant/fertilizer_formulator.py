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
from typing import Dict, Mapping, List

from plant_engine.wsda_lookup import (
    recommend_products_for_nutrient as _wsda_recommend,
)

from plant_engine import nutrient_manager

from plant_engine.utils import load_dataset

DATA_FILE = "fertilizers/fertilizer_products.json"
PRICE_FILE = "fertilizers/fertilizer_prices.json"
SOLUBILITY_FILE = "fertilizer_solubility.json"
APPLICATION_FILE = "fertilizers/fertilizer_application_methods.json"
RATE_FILE = "fertilizers/fertilizer_application_rates.json"
COMPAT_FILE = "fertilizers/fertilizer_compatibility.json"


@dataclass(frozen=True)
class Fertilizer:
    """Fertilizer product information."""

    density_kg_per_l: float
    guaranteed_analysis: Dict[str, float]
    product_name: str | None = None
    wsda_product_number: str | None = None


class FertilizerCatalog:
    """Cached access to fertilizer datasets."""

    @staticmethod
    @lru_cache(maxsize=None)
    def inventory() -> Dict[str, Fertilizer]:
        data = load_dataset(DATA_FILE)
        inv: Dict[str, Fertilizer] = {}
        for name, info in data.items():
            inv[name] = Fertilizer(
                density_kg_per_l=info.get("density_kg_per_l", 1.0),
                guaranteed_analysis=info.get("guaranteed_analysis", {}),
                product_name=info.get("product_name"),
                wsda_product_number=info.get("wsda_product_number"),
            )
        return inv

    @staticmethod
    @lru_cache(maxsize=None)
    def prices() -> Dict[str, float]:
        return load_dataset(PRICE_FILE)

    @staticmethod
    @lru_cache(maxsize=None)
    def solubility() -> Dict[str, float]:
        return load_dataset(SOLUBILITY_FILE)

    @staticmethod
    @lru_cache(maxsize=None)
    def application_methods() -> Dict[str, str]:
        return load_dataset(APPLICATION_FILE)

    @staticmethod
    @lru_cache(maxsize=None)
    def application_rates() -> Dict[str, float]:
        """Return recommended grams per liter for each fertilizer."""
        return load_dataset(RATE_FILE)

    @staticmethod
    @lru_cache(maxsize=None)
    def compatibility() -> Dict[str, Dict[str, str]]:
        """Return mixing compatibility mapping from the dataset."""
        raw = load_dataset(COMPAT_FILE)
        mapping: Dict[str, Dict[str, str]] = {}
        for fert, info in raw.items():
            if not isinstance(info, dict):
                continue
            inner: Dict[str, str] = {}
            for other, reason in info.items():
                inner[str(other)] = str(reason)
            if inner:
                mapping[fert] = inner
        return mapping

    def list_products(self) -> list[str]:
        inv = self.inventory()
        return sorted(inv.keys(), key=lambda pid: inv[pid].product_name or pid)

    def get_product_info(self, fertilizer_id: str) -> Fertilizer:
        inv = self.inventory()
        if fertilizer_id not in inv:
            raise KeyError(f"Unknown fertilizer '{fertilizer_id}'")
        return inv[fertilizer_id]


CATALOG = FertilizerCatalog()


MOLAR_MASS_CONVERSIONS = {
    "P2O5": ("P", 0.436),
    "K2O": ("K", 0.830),
}


@lru_cache(maxsize=None)
def _convert_ga_cached(items: tuple) -> dict:
    result: dict[str, float] = {}
    for k, v in items:
        if k in MOLAR_MASS_CONVERSIONS:
            element, factor = MOLAR_MASS_CONVERSIONS[k]
            result[element] = result.get(element, 0) + v * factor
        else:
            result[k] = result.get(k, 0) + v
    return result


def convert_guaranteed_analysis(ga: Mapping[str, float]) -> dict:
    """Return GA with P₂O₅/K₂O converted to elemental P and K."""

    items = []
    for k, v in ga.items():
        if v is None:
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        items.append((str(k), val))

    return _convert_ga_cached(tuple(sorted(items)))


def calculate_fertilizer_nutrients(
    plant_id: str, fertilizer_id: str, volume_ml: float
) -> Dict[str, object]:
    """Return nutrient mass (mg) for ``volume_ml`` of a fertilizer."""
    if volume_ml <= 0:
        raise ValueError("volume_ml must be positive")

    inventory = CATALOG.inventory()
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

    prices = CATALOG.prices()
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

    inventory = CATALOG.inventory()
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

    inventory = CATALOG.inventory()
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

    prices = CATALOG.prices()
    inventory = CATALOG.inventory()

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

    prices = CATALOG.prices()
    inventory = CATALOG.inventory()

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

    prices = CATALOG.prices()
    inventory = CATALOG.inventory()

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

    inventory = CATALOG.inventory()
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

    inventory = CATALOG.inventory()
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


def estimate_mix_cost_per_liter(
    schedule: Mapping[str, float], volume_l: float
) -> float:
    """Return cost per liter of solution for ``schedule`` and ``volume_l``.

    This helper builds on :func:`estimate_mix_cost` to expose the relative cost
    of a fertilizer schedule for the given solution volume. ``volume_l`` must be
    positive.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    total = estimate_mix_cost(schedule)
    return round(total / volume_l, 4)


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

    limits = CATALOG.solubility()
    warnings: Dict[str, float] = {}
    for fert_id, grams in schedule.items():
        max_g_l = limits.get(fert_id)
        if max_g_l is None:
            continue
        grams_per_l = grams / volume_l
        if grams_per_l > max_g_l:
            warnings[fert_id] = round(grams_per_l - max_g_l, 2)
    return warnings


def check_schedule_compatibility(schedule: Mapping[str, float]) -> Dict[str, Dict[str, str]]:
    """Return fertilizer incompatibilities found in ``schedule``.

    The returned mapping has each conflicting fertilizer ID mapped to the
    incompatible products and a short reason from the dataset.
    """

    ferts = [fid for fid, grams in schedule.items() if grams > 0]
    compat = CATALOG.compatibility()
    conflicts: Dict[str, Dict[str, str]] = {}
    for i, fid in enumerate(ferts):
        for other in ferts[i + 1:]:
            reason = compat.get(fid, {}).get(other) or compat.get(other, {}).get(fid)
            if reason:
                conflicts.setdefault(fid, {})[other] = reason
                conflicts.setdefault(other, {})[fid] = reason
    return conflicts


def estimate_cost_per_nutrient(fertilizer_id: str) -> Dict[str, float]:
    """Return cost per gram of each nutrient in a fertilizer product."""

    inventory = CATALOG.inventory()
    prices = CATALOG.prices()

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


def get_cheapest_product(nutrient: str) -> tuple[str, float]:
    """Return product ID and cost per gram for the cheapest source of ``nutrient``.

    The search is limited to products with defined prices. A ``KeyError`` is
    raised when no product contains the requested nutrient.
    """

    nutrient = nutrient.strip()
    if not nutrient:
        raise ValueError("nutrient must be non-empty")

    best_id: str | None = None
    best_cost: float | None = None

    for pid in list_products():
        try:
            costs = estimate_cost_per_nutrient(pid)
        except Exception:
            continue
        cost = costs.get(nutrient)
        if cost is None:
            continue
        if best_cost is None or cost < best_cost:
            best_id = pid
            best_cost = cost

    if best_id is None or best_cost is None:
        raise KeyError(f"No priced product contains nutrient '{nutrient}'")

    return best_id, best_cost




def list_products() -> list[str]:
    """Return available fertilizer product identifiers sorted by name."""
    return CATALOG.list_products()


def get_product_info(fertilizer_id: str) -> Fertilizer:
    """Return :class:`Fertilizer` details for ``fertilizer_id``."""
    return CATALOG.get_product_info(fertilizer_id)


def find_products(term: str) -> list[str]:
    """Return product IDs matching ``term`` in the ID or product name."""
    if not term:
        return []
    term = term.lower()
    results: list[str] = []
    for pid, info in CATALOG.inventory().items():
        name = (info.product_name or "").lower()
        if term in pid.lower() or term in name:
            results.append(pid)
    return sorted(results)


def get_application_method(fertilizer_id: str) -> str | None:
    """Return recommended application method for ``fertilizer_id``."""

    return CATALOG.application_methods().get(fertilizer_id)


def get_application_rate(fertilizer_id: str) -> float | None:
    """Return recommended grams per liter for ``fertilizer_id`` if defined."""

    rate = CATALOG.application_rates().get(fertilizer_id)
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def calculate_recommended_application(fertilizer_id: str, volume_l: float) -> float:
    """Return grams of fertilizer for ``volume_l`` solution using rate data."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    rate = get_application_rate(fertilizer_id)
    if rate is None:
        raise KeyError(f"Application rate for '{fertilizer_id}' is not defined")

    grams = rate * volume_l
    return round(grams, 3)


def estimate_recommended_application_cost(fertilizer_id: str, volume_l: float) -> float:
    """Return cost of fertilizer for ``volume_l`` solution using rate data."""

    grams = calculate_recommended_application(fertilizer_id, volume_l)
    return calculate_fertilizer_cost_from_mass(fertilizer_id, grams)


def recommend_wsda_products(nutrient: str, limit: int = 5) -> List[str]:
    """Return WSDA product names with high concentrations of ``nutrient``."""

    return _wsda_recommend(nutrient, limit=limit)


def estimate_deficiency_correction_cost(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float = 1.0,
) -> float:
    """Return estimated USD cost to correct nutrient deficiencies.

    The cheapest fertilizer is selected for each deficient nutrient based on
    :func:`get_cheapest_product`. ``volume_l`` represents the solution volume
    used to deliver the nutrients and must be positive.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    deficits = nutrient_manager.calculate_all_deficiencies(
        current_levels, plant_type, stage
    )
    total = 0.0
    for nutrient, deficit_ppm in deficits.items():
        if deficit_ppm <= 0:
            continue
        try:
            _, cost_per_g = get_cheapest_product(nutrient)
        except KeyError:
            continue
        grams = (deficit_ppm * volume_l) / 1000
        total += grams * cost_per_g

    return round(total, 2)


def recommend_deficiency_correction_mix(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
) -> Dict[str, float]:
    """Return fertilizer grams needed to correct nutrient deficiencies.

    Each deficient nutrient is matched with the cheapest fertilizer product
    containing it using :func:`get_cheapest_product`. The calculated grams are
    for the provided solution volume ``volume_l``.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    deficits = nutrient_manager.calculate_all_deficiencies(
        current_levels, plant_type, stage
    )
    schedule: Dict[str, float] = {}
    for nutrient, deficit_ppm in deficits.items():
        if deficit_ppm <= 0:
            continue
        try:
            fert_id, _ = get_cheapest_product(nutrient)
        except KeyError:
            continue
        grams = calculate_mass_for_target_ppm(
            fert_id, nutrient, deficit_ppm, volume_l
        )
        schedule[fert_id] = round(schedule.get(fert_id, 0.0) + grams, 3)

    return schedule


def recommend_deficiency_correction_plan(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    num_plants: int = 1,
) -> Dict[str, object]:
    """Return mix, ppm and cost info for correcting nutrient deficiencies."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

    mix = recommend_deficiency_correction_mix(
        current_levels, plant_type, stage, volume_l
    )
    cost = estimate_mix_cost(mix) if mix else 0.0
    ppm = calculate_mix_ppm(mix, volume_l) if mix else {}

    return {
        "mix": mix,
        "ppm": ppm,
        "cost_total": cost,
        "cost_per_plant": round(cost / num_plants, 4),
    }


def recommend_fertigation_mix(
    plant_type: str, stage: str, volume_l: float
) -> Dict[str, float]:
    """Return fertilizer grams for ``volume_l`` solution using cheapest products.

    The nutrient guidelines for ``plant_type`` and ``stage`` are loaded via
    :mod:`plant_engine.nutrient_manager`. For each nutrient a priced fertilizer
    product is selected using :func:`get_cheapest_product`. The amount of each
    product required to hit the guideline ppm is calculated with
    :func:`calculate_mass_for_target_ppm`. Nutrients lacking a priced source are
    skipped.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    targets = nutrient_manager.get_recommended_levels(plant_type, stage)
    if not targets:
        return {}

    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        if ppm <= 0:
            continue
        try:
            fert_id, _ = get_cheapest_product(nutrient)
        except KeyError:
            # No priced product provides this nutrient
            continue

        grams = calculate_mass_for_target_ppm(fert_id, nutrient, ppm, volume_l)
        schedule[fert_id] = round(schedule.get(fert_id, 0.0) + grams, 3)

    return schedule


def recommend_fertigation_plan(
    plant_type: str, stage: str, volume_l: float, num_plants: int = 1
) -> Dict[str, object]:
    """Return fertigation mix with ppm and cost information.

    Parameters
    ----------
    plant_type : str
        Crop type used to look up nutrient guidelines.
    stage : str
        Growth stage for the fertigation mix.
    volume_l : float
        Total solution volume in liters.
    num_plants : int, optional
        Number of plants receiving the solution. Default is ``1``.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

    mix = recommend_fertigation_mix(plant_type, stage, volume_l)
    cost = estimate_mix_cost(mix) if mix else 0.0
    ppm = calculate_mix_ppm(mix, volume_l) if mix else {}

    return {
        "mix": mix,
        "ppm": ppm,
        "cost_total": cost,
        "cost_per_plant": round(cost / num_plants, 4),
    }


def recommend_advanced_fertigation_plan(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    num_plants: int = 1,
    ph: float | None = None,
    use_synergy: bool = False,
) -> Dict[str, object]:
    """Return fertigation plan accounting for pH and nutrient synergy.

    Parameters
    ----------
    plant_type : str
        Plant type used to look up nutrient guidelines.
    stage : str
        Growth stage for the fertigation mix.
    volume_l : float
        Total solution volume in liters.
    num_plants : int, optional
        Number of plants receiving the solution. Default ``1``.
    ph : float, optional
        Solution pH used to adjust nutrient availability.
    use_synergy : bool, optional
        When ``True`` nutrient synergy factors are applied to the targets.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    if num_plants <= 0:
        raise ValueError("num_plants must be positive")
    if ph is not None and not 0 < ph <= 14:
        raise ValueError("ph must be between 0 and 14")

    if ph is not None:
        targets = nutrient_manager.get_all_ph_adjusted_levels(plant_type, stage, ph)
    else:
        targets = nutrient_manager.get_all_recommended_levels(plant_type, stage)

    if use_synergy and targets:
        from plant_engine.nutrient_synergy import apply_synergy_adjustments

        targets = apply_synergy_adjustments(targets)

    if not targets:
        return {"mix": {}, "ppm": {}, "cost_total": 0.0, "cost_per_plant": 0.0}

    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        if ppm <= 0:
            continue
        try:
            fert_id, _ = get_cheapest_product(nutrient)
        except KeyError:
            continue
        grams = calculate_mass_for_target_ppm(fert_id, nutrient, ppm, volume_l)
        schedule[fert_id] = round(schedule.get(fert_id, 0.0) + grams, 3)

    cost = estimate_mix_cost(schedule) if schedule else 0.0
    ppm = calculate_mix_ppm(schedule, volume_l) if schedule else {}

    return {
        "mix": schedule,
        "ppm": ppm,
        "cost_total": cost,
        "cost_per_plant": round(cost / num_plants, 4),
    }


__all__ = [
    "calculate_fertilizer_nutrients",
    "calculate_fertilizer_nutrients_from_mass",
    "convert_guaranteed_analysis",
    "calculate_fertilizer_cost",
    "calculate_fertilizer_cost_from_mass",
    "calculate_fertilizer_ppm",
    "estimate_mix_cost",
    "estimate_mix_cost_per_plant",
    "estimate_mix_cost_per_liter",
    "estimate_cost_breakdown",
    "get_cheapest_product",
    "estimate_deficiency_correction_cost",
    "recommend_deficiency_correction_mix",
    "recommend_deficiency_correction_plan",
    "recommend_fertigation_mix",
    "recommend_fertigation_plan",
    "recommend_advanced_fertigation_plan",
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
    "get_application_method",
    "get_application_rate",
    "calculate_recommended_application",
    "estimate_recommended_application_cost",
    "recommend_wsda_products",
    "check_schedule_compatibility",
    "CATALOG",
]

