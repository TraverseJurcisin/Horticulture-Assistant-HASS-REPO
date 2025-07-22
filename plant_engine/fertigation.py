"""Utility functions for fertigation calculations."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Mapping, Iterable

from .nutrient_manager import calculate_deficiencies, get_recommended_levels
from .utils import load_dataset

PURITY_DATA = "fertilizer_purity.json"
PRICE_DATA = "fertilizers/fertilizer_prices.json"


@lru_cache(maxsize=None)
def get_fertilizer_purity(name: str) -> Dict[str, float]:
    """Return nutrient purity factors for a fertilizer product.

    Parameters
    ----------
    name : str
        Name of the fertilizer product. Case-insensitive and uses ``_`` as word
        separator.

    Returns
    -------
    Dict[str, float]
        Mapping of nutrient code to fraction purity (0-1). Returns an empty
        dictionary if the product is unknown.
    """
    data = load_dataset(PURITY_DATA)
    return data.get(name.lower(), {})


__all__ = [
    "get_fertilizer_purity",
    "recommend_fertigation_schedule",
    "recommend_fertigation_with_water",
    "recommend_correction_schedule",
    "recommend_batch_fertigation",
    "recommend_nutrient_mix",
    "estimate_fertilizer_cost",
    "estimate_daily_nutrient_uptake",
    "recommend_uptake_fertigation",
]


def _resolve_purity(
    product: str | None,
    purity: Mapping[str, float] | None,
) -> Dict[str, float]:
    """Merge purity from a dataset product and explicit mapping."""

    merged: Dict[str, float] = {}
    if product:
        merged.update(get_fertilizer_purity(product))
    if purity:
        merged.update(purity)
    return merged


def recommend_fertigation_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, float]:
    """Return grams of fertilizer needed for a nutrient solution.

    Parameters
    ----------
    plant_type : str
        Type of plant being fertigated (e.g. "citrus").
    stage : str
        Growth stage used to look up recommended nutrient levels.
    volume_l : float
        Total solution volume in liters.
    purity : Mapping[str, float] | None, optional
        Purity fraction for each nutrient (0-1). If ``None`` all nutrients are
        assumed to be pure.
    product : str, optional
        Fertilizer product name to load purity information from the built-in
        dataset. Explicit ``purity`` values override those loaded from the
        product.
    """
    purity_map = _resolve_purity(product, purity)

    targets = get_recommended_levels(plant_type, stage)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        mg = ppm * volume_l
        grams = mg / 1000
        fraction = purity_map.get(nutrient, 1.0)
        if fraction <= 0:
            raise ValueError(f"Purity for {nutrient} must be > 0")
        schedule[nutrient] = round(grams / fraction, 3)
    return schedule


def recommend_fertigation_with_water(
    plant_type: str,
    stage: str,
    volume_l: float,
    water_profile: Mapping[str, float],
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Return fertigation schedule accounting for nutrient content in water.

    ``water_profile`` should map nutrient codes to baseline ppm values.
    Any analytes exceeding thresholds in :mod:`plant_engine.water_quality`
    will appear in the second returned mapping.
    """

    from .water_quality import interpret_water_profile

    baseline, warnings = interpret_water_profile(water_profile)
    purity_map = _resolve_purity(product, purity)

    targets = get_recommended_levels(plant_type, stage)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        deficit_ppm = max(0.0, ppm - baseline.get(nutrient, 0.0))
        mg = deficit_ppm * volume_l
        grams = mg / 1000
        fraction = purity_map.get(nutrient, 1.0)
        if fraction <= 0:
            raise ValueError(f"Purity for {nutrient} must be > 0")
        schedule[nutrient] = round(grams / fraction, 3)

    return schedule, warnings


def recommend_correction_schedule(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float] | None,
    *,
    product: str | None = None,
) -> Dict[str, float]:
    """Return grams of fertilizer needed to correct deficiencies.

    ``current_levels`` is the measured nutrient concentration in the solution.
    Any nutrient below the guideline for ``plant_type`` and ``stage`` will be
    included in the returned mapping.
    """
    purity_map = _resolve_purity(product, purity)
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    corrections: Dict[str, float] = {}
    for nutrient, ppm in deficits.items():
        mg = ppm * volume_l
        grams = mg / 1000
        frac = purity_map.get(nutrient, 1.0)
        if frac <= 0:
            raise ValueError(f"Purity for {nutrient} must be > 0")
        corrections[nutrient] = round(grams / frac, 3)
    return corrections


def recommend_batch_fertigation(
    plants: Iterable[tuple[str, str]],
    volume_l: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, Dict[str, float]]:
    """Return fertigation schedules for multiple plants.

    Parameters
    ----------
    plants : Iterable[tuple[str, str]]
        Iterable of ``(plant_type, stage)`` tuples.
    volume_l : float
        Solution volume in liters shared by each plant.
    purity : Mapping[str, float] | None, optional
        Purity factors for nutrients. Overrides values from ``product``.
    product : str, optional
        Fertilizer product identifier used to lookup purity.
    """

    schedules: Dict[str, Dict[str, float]] = {}
    for plant_type, stage in plants:
        key = f"{plant_type}-{stage}"
        schedules[key] = recommend_fertigation_schedule(
            plant_type,
            stage,
            volume_l,
            purity,
            product=product,
        )
    return schedules


def recommend_nutrient_mix(
    plant_type: str,
    stage: str,
    volume_l: float,
    current_levels: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
) -> Dict[str, float]:
    """Return grams of fertilizer required to meet nutrient targets.

    Parameters
    ----------
    plant_type : str
        Crop type used to look up guidelines.
    stage : str
        Growth stage for nutrient targets.
    volume_l : float
        Total solution volume in liters.
    current_levels : Mapping[str, float] | None
        Current nutrient concentration (ppm). If provided, only deficits are
        supplied. If ``None`` full guideline amounts are used.
    fertilizers : Mapping[str, str] | None
        Mapping of nutrient code (``"N"``, ``"P"``, ``"K"``) to fertilizer
        product identifiers from :data:`fertilizer_purity.json`.
    purity_overrides : Mapping[str, float] | None
        Optional overrides for nutrient purity fractions.
    include_micro : bool, optional
        If ``True`` micronutrients are also included using
        :mod:`plant_engine.micro_manager` guidelines.
    micro_fertilizers : Mapping[str, str] | None, optional
        Mapping of micronutrient code (e.g. ``"Fe"``) to fertilizer product
        identifiers. Only used when ``include_micro`` is ``True``.
    """

    if fertilizers is None:
        fertilizers = {"N": "urea", "P": "map", "K": "kcl"}
    if micro_fertilizers is None:
        micro_fertilizers = {
            "Fe": "chelated_fe",
            "Mn": "chelated_mn",
            "Zn": "chelated_zn",
            "B": "boric_acid",
            "Cu": "chelated_cu",
            "Mo": "sodium_molybdate",
        }

    if current_levels is None:
        deficits = get_recommended_levels(plant_type, stage)
    else:
        deficits = calculate_deficiencies(current_levels, plant_type, stage)

    if include_micro:
        from .micro_manager import (
            get_recommended_levels as get_micro_levels,
            calculate_deficiencies as calc_micro,
        )
        if current_levels is None:
            micro_def = get_micro_levels(plant_type, stage)
        else:
            micro_def = calc_micro(current_levels, plant_type, stage)
        deficits.update(micro_def)

    schedule: Dict[str, float] = {}
    for nutrient, target_ppm in deficits.items():
        fert = fertilizers.get(nutrient)
        if include_micro and fert is None:
            fert = micro_fertilizers.get(nutrient)
        if not fert:
            continue
        purity = get_fertilizer_purity(fert).get(nutrient, 1.0)
        if purity_overrides and nutrient in purity_overrides:
            purity = purity_overrides[nutrient]
        if purity <= 0:
            raise ValueError(f"Purity for {nutrient} in {fert} must be > 0")
        grams_nutrient = (target_ppm * volume_l) / 1000
        grams_fert = grams_nutrient / purity
        schedule[fert] = round(grams_fert, 3)

    return schedule


def estimate_daily_nutrient_uptake(
    plant_type: str,
    stage: str,
    daily_water_ml: float,
) -> Dict[str, float]:
    """Return estimated nutrient uptake per day in milligrams.

    The calculation multiplies recommended ppm values by the amount of
    irrigation water used each day (in milliliters).
    """

    if daily_water_ml < 0:
        raise ValueError("daily_water_ml must be non-negative")

    targets = get_recommended_levels(plant_type, stage)
    liters = daily_water_ml / 1000
    uptake: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        uptake[nutrient] = round(ppm * liters, 2)
    return uptake

def recommend_uptake_fertigation(
    plant_type: str,
    stage: str,
    *,
    num_plants: int = 1,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
) -> Dict[str, float]:
    """Return grams of fertilizer for daily nutrient uptake targets."""

    from .nutrient_uptake import get_daily_uptake

    if num_plants <= 0:
        raise ValueError("num_plants must be positive")

    uptake = get_daily_uptake(plant_type, stage)
    if not uptake:
        return {}

    if fertilizers is None:
        fertilizers = {"N": "urea", "P": "map", "K": "kcl"}

    schedule: Dict[str, float] = {}
    for nutrient, mg_per_day in uptake.items():
        fert = fertilizers.get(nutrient)
        if not fert:
            continue
        purity = get_fertilizer_purity(fert).get(nutrient, 0.0)
        if purity_overrides and nutrient in purity_overrides:
            purity = purity_overrides[nutrient]
        if purity <= 0:
            raise ValueError(f"Purity for {nutrient} in {fert} must be > 0")
        grams = (mg_per_day * num_plants) / 1000 / purity
        schedule[fert] = round(schedule.get(fert, 0.0) + grams, 3)

    return schedule


def estimate_fertilizer_cost(schedule: Mapping[str, float]) -> float:
    """Return estimated cost for a fertigation schedule.

    The ``schedule`` should map fertilizer identifiers to grams of product.
    Prices are loaded from :data:`PRICE_DATA` and assumed to be in currency
    units per kilogram. Unknown products contribute no cost.
    """

    prices = load_dataset(PRICE_DATA)
    total = 0.0
    for product, grams in schedule.items():
        kg = grams / 1000
        price_per_kg = prices.get(product, 0.0)
        total += kg * price_per_kg
    return round(total, 2)


