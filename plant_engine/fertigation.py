"""Utility functions for fertigation calculations."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Mapping, Iterable

from .nutrient_manager import calculate_deficiencies, get_recommended_levels
from .utils import load_dataset

PURITY_DATA = "fertilizer_purity.json"


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
    "recommend_correction_schedule",
    "recommend_batch_fertigation",
    "recommend_nutrient_mix",
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
) -> Dict[str, float]:
    """Return grams of each fertilizer required to meet N/P/K targets.

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
    """

    if fertilizers is None:
        fertilizers = {"N": "urea", "P": "map", "K": "kcl"}

    if current_levels is None:
        deficits = get_recommended_levels(plant_type, stage)
    else:
        deficits = calculate_deficiencies(current_levels, plant_type, stage)

    schedule: Dict[str, float] = {}
    for nutrient, target_ppm in deficits.items():
        fert = fertilizers.get(nutrient)
        if not fert:
            continue
        purity = get_fertilizer_purity(fert).get(nutrient, 0.0)
        if purity_overrides and nutrient in purity_overrides:
            purity = purity_overrides[nutrient]
        if purity <= 0:
            raise ValueError(f"Purity for {nutrient} in {fert} must be > 0")
        grams_nutrient = (target_ppm * volume_l) / 1000
        grams_fert = grams_nutrient / purity
        schedule[fert] = round(schedule.get(fert, 0) + grams_fert, 3)

    return schedule

