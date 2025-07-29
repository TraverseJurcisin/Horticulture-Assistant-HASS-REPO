"""Utility functions for fertigation calculations."""

from __future__ import annotations

from functools import lru_cache
from datetime import date, timedelta
from typing import Dict, Mapping, Iterable

from .nutrient_interactions import check_imbalances
from .toxicity_manager import check_toxicities

from .nutrient_manager import (
    calculate_deficiencies,
    get_recommended_levels,
    calculate_all_deficiencies,
    get_all_recommended_levels,
    get_synergy_adjusted_levels,
    calculate_all_deficiencies_with_synergy,
)
from .utils import load_dataset, normalize_key, stage_value

FOLIAR_DATA = "foliar_feed_guidelines.json"
INTERVAL_DATA = "foliar_feed_intervals.json"
FERTIGATION_INTERVAL_DATA = "fertigation_intervals.json"
FOLIAR_VOLUME_DATA = "foliar_spray_volume.json"
FERTIGATION_VOLUME_DATA = "fertigation_volume.json"

PURITY_DATA = "fertilizer_purity.json"
EC_FACTOR_DATA = "ion_ec_factors.json"
STOCK_DATA = "stock_solution_concentrations.json"
SOLUBILITY_DATA = "fertilizer_solubility.json"
RECIPE_DATA = "fertigation_recipes.json"
STOCK_RECIPE_DATA = "stock_solution_recipes.json"
LOSS_FACTOR_DATA = "fertigation_loss_factors.json"
INJECTOR_DATA = "fertigation_injectors.json"

_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(INTERVAL_DATA)
_FERTIGATION_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(
    FERTIGATION_INTERVAL_DATA
)
_FOLIAR_VOLUME: Dict[str, Dict[str, float]] = load_dataset(FOLIAR_VOLUME_DATA)
_FERTIGATION_VOLUME: Dict[str, Dict[str, float]] = load_dataset(FERTIGATION_VOLUME_DATA)
_STOCK_SOLUTIONS: Dict[str, Dict[str, float]] = load_dataset(STOCK_DATA)
_NUTRIENT_STOCK_MAP = {
    nutrient: sid
    for sid, nutrients in _STOCK_SOLUTIONS.items()
    for nutrient in nutrients
}
_SOLUBILITY_LIMITS: Dict[str, float] = load_dataset(SOLUBILITY_DATA)
_RECIPES: Dict[str, Dict[str, Mapping[str, float]]] = load_dataset(RECIPE_DATA)
_STOCK_RECIPES: Dict[str, Dict[str, Mapping[str, float]]] = load_dataset(STOCK_RECIPE_DATA)
_LOSS_FACTORS: Dict[str, Dict[str, float]] = load_dataset(LOSS_FACTOR_DATA)
_INJECTORS: Dict[str, float] = load_dataset(INJECTOR_DATA)


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


@lru_cache(maxsize=None)
def get_ec_factors() -> Dict[str, float]:
    """Return EC contribution factors for nutrient ions."""
    return load_dataset(EC_FACTOR_DATA)


@lru_cache(maxsize=None)
def get_solubility_limits() -> Dict[str, float]:
    """Return maximum solubility in g/L for fertilizers."""
    return {
        normalize_key(k): float(v)
        for k, v in _SOLUBILITY_LIMITS.items()
        if isinstance(v, (int, float))
    }


@lru_cache(maxsize=None)
def get_fertigation_recipe(plant_type: str, stage: str) -> Dict[str, float]:
    """Return grams per liter of fertilizers for a plant stage."""
    plant = _RECIPES.get(normalize_key(plant_type), {})
    recipe = plant.get(normalize_key(stage)) if isinstance(plant, Mapping) else None
    if not isinstance(recipe, Mapping):
        return {}
    result: Dict[str, float] = {}
    for fert, grams in recipe.items():
        try:
            result[fert] = float(grams)
        except (TypeError, ValueError):
            continue
    return result


def apply_fertigation_recipe(
    plant_type: str, stage: str, volume_l: float
) -> Dict[str, float]:
    """Return fertilizer grams for ``volume_l`` based on a recipe."""
    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    base = get_fertigation_recipe(plant_type, stage)
    return {fid: round(g * volume_l, 3) for fid, g in base.items()}


@lru_cache(maxsize=None)
def get_stock_solution_recipe(plant_type: str, stage: str) -> Dict[str, float]:
    """Return stock solution mL per liter for a plant stage."""
    plant = _STOCK_RECIPES.get(normalize_key(plant_type), {})
    recipe = plant.get(normalize_key(stage)) if isinstance(plant, Mapping) else None
    if not isinstance(recipe, Mapping):
        return {}
    result: Dict[str, float] = {}
    for sid, ml in recipe.items():
        try:
            result[sid] = float(ml)
        except (TypeError, ValueError):
            continue
    return result


def apply_stock_solution_recipe(
    plant_type: str, stage: str, volume_l: float
) -> Dict[str, float]:
    """Return stock solution volumes (mL) for ``volume_l`` injection."""
    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    base = get_stock_solution_recipe(plant_type, stage)
    return {sid: round(ml * volume_l, 2) for sid, ml in base.items()}


@lru_cache(maxsize=None)
def get_loss_factors(plant_type: str) -> Dict[str, float]:
    """Return nutrient loss adjustment factors for ``plant_type``."""

    factors = {}
    base = _LOSS_FACTORS.get("default", {})
    crop = _LOSS_FACTORS.get(normalize_key(plant_type), {})
    for k, v in {**base, **crop}.items():
        try:
            factors[k] = float(v)
        except (TypeError, ValueError):
            continue
    return factors


def apply_loss_factors(schedule: Mapping[str, float], plant_type: str) -> Dict[str, float]:
    """Return ``schedule`` with grams increased by loss factors."""

    factors = get_loss_factors(plant_type)
    adjusted: Dict[str, float] = {}
    for fert, grams in schedule.items():
        factor = factors.get(fert, 0.0)
        adjusted[fert] = round(grams * (1.0 + factor), 3)
    return adjusted


@lru_cache(maxsize=None)
def get_injection_ratio(injector: str) -> float | None:
    """Return dilution ratio for an injector model if known."""

    ratio = _INJECTORS.get(normalize_key(injector))
    try:
        return float(ratio) if ratio is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def calculate_injection_volumes(
    schedule: Mapping[str, float], volume_l: float, injector: str
) -> Dict[str, float]:
    """Return injection volumes (mL) for a fertilizer schedule.

    ``schedule`` maps fertilizer IDs to total grams required for ``volume_l`` of
    solution. ``injector`` is looked up in :data:`INJECTOR_DATA` to obtain the
    dilution ratio. Pure fertilizer volumes are calculated using the inventory
    density and divided by the ratio to determine the injected amount.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    ratio = get_injection_ratio(injector)
    if ratio is None or ratio <= 0:
        raise KeyError(f"Unknown injector '{injector}'")

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        CATALOG,
    )

    inventory = CATALOG.inventory()
    volumes: Dict[str, float] = {}
    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        if fert_id not in inventory:
            raise KeyError(f"Unknown fertilizer '{fert_id}'")
        density = inventory[fert_id].density_kg_per_l
        if density <= 0:
            raise ValueError(f"Invalid density for '{fert_id}'")
        liters = grams / (density * 1000)
        volumes[fert_id] = round(liters * 1000 / ratio, 3)

    return volumes


def recommend_loss_adjusted_fertigation(
    plant_type: str,
    stage: str,
    volume_l: float,
    water_profile: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[
    Dict[str, float],
    float,
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """Return fertigation schedule adjusted for nutrient losses.

    Parameters
    ----------
    use_synergy : bool, optional
        When ``True`` nutrient synergy factors are applied before loss
        adjustments.
    """

    schedule, total, breakdown, warnings, diagnostics = recommend_precise_fertigation(
        plant_type,
        stage,
        volume_l,
        water_profile,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        include_micro=include_micro,
        micro_fertilizers=micro_fertilizers,
        use_synergy=use_synergy,
    )

    adjusted = apply_loss_factors(schedule, plant_type)

    return adjusted, total, breakdown, warnings, diagnostics


@lru_cache(maxsize=None)
def get_foliar_guidelines(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended foliar feed ppm for a plant stage."""
    data = load_dataset(FOLIAR_DATA)
    plant = data.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


def recommend_foliar_feed(
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, float]:
    """Return grams of fertilizer for foliar spray solution."""
    purity_map = _resolve_purity(product, purity)
    targets = get_foliar_guidelines(plant_type, stage)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        schedule[nutrient] = _ppm_to_grams(
            float(ppm), volume_l, purity_map.get(nutrient, 1.0)
        )
    return schedule


@lru_cache(maxsize=None)
def get_foliar_feed_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between foliar feeds."""

    value = stage_value(_INTERVALS, plant_type, stage)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def next_foliar_feed_date(
    plant_type: str, stage: str | None, last_date: date
) -> date | None:
    """Return the next recommended foliar feed date."""

    interval = get_foliar_feed_interval(plant_type, stage)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)


@lru_cache(maxsize=None)
def get_foliar_spray_volume(plant_type: str, stage: str | None = None) -> float | None:
    """Return recommended foliar spray volume per plant in milliliters."""

    value = stage_value(_FOLIAR_VOLUME, plant_type, stage)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def estimate_spray_solution_volume(
    num_plants: int, plant_type: str, stage: str | None = None
) -> float | None:
    """Return total spray solution volume in liters for ``num_plants``."""

    if num_plants <= 0:
        raise ValueError("num_plants must be positive")
    per_plant = get_foliar_spray_volume(plant_type, stage)
    if per_plant is None:
        return None
    total_ml = per_plant * num_plants
    return round(total_ml / 1000, 2)


@lru_cache(maxsize=None)
def get_fertigation_volume(plant_type: str, stage: str | None = None) -> float | None:
    """Return recommended fertigation volume per plant in milliliters."""

    value = stage_value(_FERTIGATION_VOLUME, plant_type, stage)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def estimate_fertigation_solution_volume(
    num_plants: int, plant_type: str, stage: str | None = None
) -> float | None:
    """Return total fertigation solution volume in liters for ``num_plants``."""

    if num_plants <= 0:
        raise ValueError("num_plants must be positive")
    per_plant = get_fertigation_volume(plant_type, stage)
    if per_plant is None:
        return None
    total_ml = per_plant * num_plants
    return round(total_ml / 1000, 2)


@lru_cache(maxsize=None)
def get_fertigation_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between fertigation events."""

    value = stage_value(_FERTIGATION_INTERVALS, plant_type, stage)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def next_fertigation_date(
    plant_type: str, stage: str | None, last_date: date
) -> date | None:
    """Return the next recommended fertigation date."""

    interval = get_fertigation_interval(plant_type, stage)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)


__all__ = [
    "get_fertilizer_purity",
    "get_solubility_limits",
    "get_foliar_guidelines",
    "recommend_foliar_feed",
    "get_foliar_feed_interval",
    "next_foliar_feed_date",
    "get_foliar_spray_volume",
    "estimate_spray_solution_volume",
    "get_fertigation_volume",
    "estimate_fertigation_solution_volume",
    "get_fertigation_interval",
    "next_fertigation_date",
    "recommend_fertigation_schedule",
    "recommend_fertigation_with_water",
    "recommend_correction_schedule",
    "recommend_batch_fertigation",
    "recommend_nutrient_mix",
    "recommend_nutrient_mix_with_water",
    "estimate_daily_nutrient_uptake",
    "recommend_uptake_fertigation",
    "recommend_nutrient_mix_with_cost",
    "recommend_nutrient_mix_with_cost_breakdown",
    "recommend_loss_compensated_mix",
    "recommend_recovery_adjusted_schedule",
    "get_fertigation_recipe",
    "apply_fertigation_recipe",
    "get_stock_solution_recipe",
    "apply_stock_solution_recipe",
    "generate_fertigation_plan",
    "calculate_mix_nutrients",
    "estimate_solution_ec",
    "estimate_stage_cost",
    "estimate_cycle_cost",
    "estimate_weekly_fertigation_cost",
    "generate_cycle_fertigation_plan",
    "generate_cycle_fertigation_plan_with_cost",
    "optimize_fertigation_schedule",
    "recommend_precise_fertigation",
    "recommend_precise_fertigation_with_injection",
    "recommend_cost_optimized_fertigation_with_injection",
    "recommend_rootzone_fertigation",
    "recommend_temperature_adjusted_fertigation",
    "get_loss_factors",
    "apply_loss_factors",
    "get_injection_ratio",
    "calculate_injection_volumes",
    "recommend_loss_adjusted_fertigation",
    "grams_to_ppm",
    "check_solubility_limits",
    "recommend_stock_solution_injection",
    "validate_fertigation_schedule",
    "summarize_fertigation_schedule",
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


def _ppm_to_grams(ppm: float, volume_l: float, purity: float) -> float:
    """Return grams of fertilizer for ``ppm`` target in ``volume_l``.

    Parameters
    ----------
    ppm : float
        Parts per million nutrient concentration.
    volume_l : float
        Solution volume in liters.
    purity : float
        Fractional nutrient purity (0-1). Must be greater than zero.
    """

    if purity <= 0:
        raise ValueError("purity must be > 0")
    mg = ppm * volume_l
    return round((mg / 1000) / purity, 3)


def grams_to_ppm(grams: float, volume_l: float, purity: float) -> float:
    """Return nutrient ppm for ``grams`` dissolved in ``volume_l`` solution.

    Parameters
    ----------
    grams : float
        Fertilizer mass in grams.
    volume_l : float
        Final solution volume in liters. Must be greater than zero.
    purity : float
        Fractional nutrient purity (0-1). Must be greater than zero.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be > 0")
    if purity <= 0:
        raise ValueError("purity must be > 0")

    mg = grams * 1000 * purity
    return round(mg / volume_l, 2)


def check_solubility_limits(
    schedule: Mapping[str, float], volume_l: float
) -> Dict[str, float]:
    """Delegate to :func:`fertilizer_formulator.check_solubility_limits`."""

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        check_solubility_limits as _check,
    )

    return _check(schedule, volume_l)


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
        schedule[nutrient] = _ppm_to_grams(ppm, volume_l, purity_map.get(nutrient, 1.0))
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
        schedule[nutrient] = _ppm_to_grams(
            deficit_ppm, volume_l, purity_map.get(nutrient, 1.0)
        )

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
        corrections[nutrient] = _ppm_to_grams(
            ppm, volume_l, purity_map.get(nutrient, 1.0)
        )
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
    use_synergy: bool = False,
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
    use_synergy : bool, optional
        When ``True`` nutrient guidelines are adjusted using synergy factors
        before calculating deficits.
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

    if include_micro or use_synergy:
        if current_levels is None:
            if use_synergy:
                deficits = get_synergy_adjusted_levels(plant_type, stage)
            else:
                deficits = get_all_recommended_levels(plant_type, stage)
        else:
            if use_synergy:
                deficits = calculate_all_deficiencies_with_synergy(
                    current_levels, plant_type, stage
                )
            else:
                deficits = calculate_all_deficiencies(
                    current_levels, plant_type, stage
                )
        if not include_micro:
            macros = {"N", "P", "K", "Ca", "Mg", "S"}
            deficits = {n: v for n, v in deficits.items() if n in macros}
    else:
        if current_levels is None:
            deficits = get_recommended_levels(plant_type, stage)
        else:
            deficits = calculate_deficiencies(current_levels, plant_type, stage)

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


def recommend_nutrient_mix_with_water(
    plant_type: str,
    stage: str,
    volume_l: float,
    water_profile: Mapping[str, float],
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Return fertilizer mix adjusted for nutrients in the irrigation water."""

    from .water_quality import interpret_water_profile

    baseline, warnings = interpret_water_profile(water_profile)
    schedule = recommend_nutrient_mix(
        plant_type,
        stage,
        volume_l,
        current_levels=baseline,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        include_micro=include_micro,
        micro_fertilizers=micro_fertilizers,
        use_synergy=use_synergy,
    )

    return schedule, warnings


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


def recommend_nutrient_mix_with_cost(
    plant_type: str,
    stage: str,
    volume_l: float,
    current_levels: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[Dict[str, float], float]:
    """Return fertigation mix and estimated cost for a plant stage."""

    schedule = recommend_nutrient_mix(
        plant_type,
        stage,
        volume_l,
        current_levels,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        include_micro=include_micro,
        micro_fertilizers=micro_fertilizers,
        use_synergy=use_synergy,
    )

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
    )

    cost = estimate_mix_cost(schedule)
    return schedule, cost


def recommend_nutrient_mix_with_cost_breakdown(
    plant_type: str,
    stage: str,
    volume_l: float,
    current_levels: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[Dict[str, float], float, Dict[str, float]]:
    """Return fertigation mix with total and per-nutrient cost estimates."""

    schedule, total = recommend_nutrient_mix_with_cost(
        plant_type,
        stage,
        volume_l,
        current_levels,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        include_micro=include_micro,
        micro_fertilizers=micro_fertilizers,
        use_synergy=use_synergy,
    )

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_cost_breakdown,
    )

    breakdown = estimate_cost_breakdown(schedule)
    return schedule, total, breakdown


def generate_fertigation_plan(
    plant_type: str,
    stage: str,
    days: int,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[int, Dict[str, float]]:
    """Return daily fertigation schedules for ``days`` days.

    This convenience helper pulls the recommended daily irrigation volume from
    :func:`irrigation_manager.get_daily_irrigation_target` and generates a
    fertilizer schedule for each day using
    :func:`recommend_fertigation_schedule`.
    """

    from .irrigation_manager import get_daily_irrigation_target

    if days <= 0:
        raise ValueError("days must be positive")

    daily_ml = get_daily_irrigation_target(plant_type, stage)
    if daily_ml <= 0:
        return {}

    volume_l = daily_ml / 1000
    plan: Dict[int, Dict[str, float]] = {}
    for day in range(1, days + 1):
        plan[day] = recommend_fertigation_schedule(
            plant_type,
            stage,
            volume_l,
            purity,
            product=product,
        )
    return plan


def recommend_precise_fertigation(
    plant_type: str,
    stage: str,
    volume_l: float,
    water_profile: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[
    Dict[str, float],
    float,
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
]:
    """Return fertigation schedule with cost, diagnostics and optional water adjustments."""

    if water_profile is not None:
        schedule, warnings = recommend_nutrient_mix_with_water(
            plant_type,
            stage,
            volume_l,
            water_profile,
            fertilizers=fertilizers,
            purity_overrides=purity_overrides,
            include_micro=include_micro,
            micro_fertilizers=micro_fertilizers,
            use_synergy=use_synergy,
        )
    else:
        schedule = recommend_nutrient_mix(
            plant_type,
            stage,
            volume_l,
            current_levels=None,
            fertilizers=fertilizers,
            purity_overrides=purity_overrides,
            include_micro=include_micro,
            micro_fertilizers=micro_fertilizers,
            use_synergy=use_synergy,
        )
        warnings = {}

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
        estimate_cost_breakdown,
    )

    try:
        total = estimate_mix_cost(schedule)
        breakdown = estimate_cost_breakdown(schedule)
    except KeyError:
        total = 0.0
        breakdown = {}
    diagnostics = validate_fertigation_schedule(schedule, volume_l, plant_type)

    return schedule, total, breakdown, warnings, diagnostics


def recommend_precise_fertigation_with_injection(
    plant_type: str,
    stage: str,
    volume_l: float,
    water_profile: Mapping[str, float] | None = None,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
    use_synergy: bool = False,
) -> tuple[
    Dict[str, float],
    float,
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, float]],
    Dict[str, float],
]:
    """Return precise fertigation plan with stock solution injection volumes."""

    schedule, total, breakdown, warnings, diagnostics = recommend_precise_fertigation(
        plant_type,
        stage,
        volume_l,
        water_profile,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        include_micro=include_micro,
        micro_fertilizers=micro_fertilizers,
        use_synergy=use_synergy,
    )

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        calculate_mix_ppm,
    )

    ppm_levels = calculate_mix_ppm(schedule, volume_l)
    injection = recommend_stock_solution_injection(ppm_levels, volume_l)

    return (
        schedule,
        total,
        breakdown,
        warnings,
        diagnostics,
        injection,
    )


def recommend_rootzone_fertigation(
    plant_type: str,
    stage: str,
    rootzone: "RootZone",
    available_ml: float,
    expected_et_ml: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> tuple[float, Dict[str, float]]:
    """Return irrigation volume (mL) and fertilizer grams for the root zone.

    This helper combines :func:`irrigation_manager.recommend_irrigation_volume`
    with :func:`recommend_fertigation_schedule` to generate a fertigation plan
    based on the current root zone status.
    """

    from .irrigation_manager import recommend_irrigation_volume

    volume_ml = recommend_irrigation_volume(
        rootzone,
        available_ml,
        expected_et_ml,
    )

    if volume_ml <= 0:
        return 0.0, {}

    schedule = recommend_fertigation_schedule(
        plant_type,
        stage,
        volume_ml / 1000,
        purity,
        product=product,
    )

    return volume_ml, schedule


def recommend_loss_compensated_mix(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    losses: Iterable[str] = ("leaching", "volatilization"),
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    include_micro: bool = False,
    micro_fertilizers: Mapping[str, str] | None = None,
) -> Dict[str, float]:
    """Return fertigation mix adjusted for nutrient losses."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    if include_micro:
        targets = get_all_recommended_levels(plant_type, stage)
    else:
        targets = get_recommended_levels(plant_type, stage)

    adjusted = dict(targets)
    if "leaching" in losses:
        from .nutrient_leaching import compensate_for_leaching

        adjusted = compensate_for_leaching(adjusted, plant_type)
    if "volatilization" in losses:
        from .nutrient_volatilization import compensate_for_volatilization

        adjusted = compensate_for_volatilization(adjusted, plant_type)

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

    schedule: Dict[str, float] = {}
    for nutrient, ppm in adjusted.items():
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
        grams = (ppm * volume_l) / 1000 / purity
        schedule[fert] = round(schedule.get(fert, 0.0) + grams, 3)

    return schedule


def recommend_recovery_adjusted_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    recovery_factors: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
    purity: Mapping[str, float] | None = None,
) -> Dict[str, float]:
    """Return fertigation schedule adjusted for nutrient recovery factors."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    purity_map = _resolve_purity(product, purity)

    targets = get_recommended_levels(plant_type, stage)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        if recovery_factors and nutrient in recovery_factors:
            factor = recovery_factors[nutrient]
        else:
            from .nutrient_recovery import get_recovery_factor

            factor = get_recovery_factor(nutrient, plant_type)
        if factor <= 0:
            factor = 1.0
        adjusted_ppm = ppm / factor
        schedule[nutrient] = _ppm_to_grams(
            adjusted_ppm, volume_l, purity_map.get(nutrient, 1.0)
        )
    return schedule


def recommend_temperature_adjusted_fertigation(
    plant_type: str,
    stage: str,
    volume_l: float,
    root_temp_c: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, float]:
    """Return fertigation schedule adjusted for root temperature uptake.

    Nutrient targets are scaled by factors from
    :data:`root_temperature_uptake.json` before converting to grams.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    from .nutrient_manager import get_temperature_adjusted_levels

    purity_map = _resolve_purity(product, purity)
    targets = get_temperature_adjusted_levels(plant_type, stage, root_temp_c)
    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        schedule[nutrient] = _ppm_to_grams(
            ppm, volume_l, purity_map.get(nutrient, 1.0)
        )
    return schedule


def calculate_mix_nutrients(schedule: Mapping[str, float]) -> Dict[str, float]:
    """Return elemental nutrient totals for a fertilizer mix."""

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        calculate_mix_nutrients as _calc,
    )

    return _calc(schedule)


def estimate_solution_ec(schedule: Mapping[str, float]) -> float:
    """Return estimated EC (dS/m) for a nutrient solution."""

    factors = get_ec_factors()
    total_us_cm = 0.0
    for nutrient, ppm in schedule.items():
        factor = factors.get(nutrient, 0.0)
        total_us_cm += float(ppm) * factor
    return round(total_us_cm / 1000, 3)


def _schedule_from_totals(
    totals: Mapping[str, float],
    num_plants: int,
    fertilizers: Mapping[str, str],
    purity_overrides: Mapping[str, float] | None = None,
) -> Dict[str, float]:
    """Return fertilizer grams needed for nutrient totals."""

    schedule: Dict[str, float] = {}
    for nutrient, mg in totals.items():
        fert = fertilizers.get(nutrient)
        if not fert:
            continue
        purity = get_fertilizer_purity(fert).get(nutrient, 0.0)
        if purity <= 0:
            try:
                from custom_components.horticulture_assistant.fertilizer_formulator import (
                    get_product_info,
                    convert_guaranteed_analysis,
                )

                info = get_product_info(fert)
                ga = convert_guaranteed_analysis(info.guaranteed_analysis)
                purity = ga.get(nutrient, 0.0)
            except Exception:
                purity = 0.0
        if purity_overrides and nutrient in purity_overrides:
            purity = purity_overrides[nutrient]
        if purity <= 0:
            # Fall back to assuming pure nutrient to avoid divide errors
            purity = 1.0
        grams = mg * num_plants / 1000 / purity
        schedule[fert] = round(schedule.get(fert, 0.0) + grams, 3)
    return schedule


def estimate_stage_cost(
    plant_type: str,
    stage: str,
    *,
    num_plants: int = 1,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
) -> float:
    """Return estimated fertilizer cost for a growth stage."""

    from .nutrient_uptake import estimate_stage_totals
    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
    )

    totals = estimate_stage_totals(plant_type, stage)
    if not totals:
        return 0.0

    if fertilizers is None:
        fertilizers = {
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        }

    schedule = _schedule_from_totals(totals, num_plants, fertilizers, purity_overrides)
    return estimate_mix_cost(schedule)


def estimate_cycle_cost(
    plant_type: str,
    *,
    num_plants: int = 1,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
) -> float:
    """Return estimated fertilizer cost for the entire crop cycle."""

    from .nutrient_uptake import estimate_total_uptake
    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
    )

    totals = estimate_total_uptake(plant_type)
    if not totals:
        return 0.0

    if fertilizers is None:
        fertilizers = {
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        }

    schedule = _schedule_from_totals(totals, num_plants, fertilizers, purity_overrides)
    return estimate_mix_cost(schedule)


def estimate_weekly_fertigation_cost(
    plant_type: str,
    stage: str,
    daily_volume_l: float,
    *,
    fertilizers: Mapping[str, str] | None = None,
    purity_overrides: Mapping[str, float] | None = None,
    use_synergy: bool = False,
) -> float:
    """Return estimated cost for a week of fertigation at ``daily_volume_l``.

    This helper uses :func:`recommend_nutrient_mix_with_cost` to calculate the
    daily fertilizer mix and multiplies the result by seven days.
    """

    if daily_volume_l <= 0:
        raise ValueError("daily_volume_l must be positive")

    _, cost = recommend_nutrient_mix_with_cost(
        plant_type,
        stage,
        daily_volume_l,
        fertilizers=fertilizers,
        purity_overrides=purity_overrides,
        use_synergy=use_synergy,
    )
    return round(cost * 7, 2)


def optimize_fertigation_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    include_micro: bool = False,
) -> tuple[Dict[str, float], float]:
    """Return lowest cost fertilizer mix for a plant stage."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        get_cheapest_product,
        estimate_mix_cost,
    )

    if include_micro:
        targets = get_all_recommended_levels(plant_type, stage)
    else:
        targets = get_recommended_levels(plant_type, stage)

    schedule: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        try:
            product, _ = get_cheapest_product(nutrient)
        except KeyError:
            continue
        purity = get_fertilizer_purity(product).get(nutrient, 1.0)
        grams = _ppm_to_grams(ppm, volume_l, purity)
        schedule[product] = round(schedule.get(product, 0.0) + grams, 3)

    cost = estimate_mix_cost(schedule) if schedule else 0.0
    return schedule, cost


def recommend_cost_optimized_fertigation_with_injection(
    plant_type: str,
    stage: str,
    volume_l: float,
    *,
    include_micro: bool = False,
) -> tuple[Dict[str, float], float, Dict[str, float]]:
    """Return lowest cost fertigation mix and injection volumes.

    This helper combines :func:`optimize_fertigation_schedule` with
    stock solution injection calculations so the resulting schedule can
    be applied directly by nutrient injectors.
    """

    schedule, cost = optimize_fertigation_schedule(
        plant_type, stage, volume_l, include_micro=include_micro
    )

    if not schedule:
        return {}, 0.0, {}

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        calculate_mix_ppm,
    )

    ppm_levels = calculate_mix_ppm(schedule, volume_l)
    injection = recommend_stock_solution_injection(ppm_levels, volume_l)

    return schedule, cost, injection


def generate_cycle_fertigation_plan(
    plant_type: str,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Return fertigation plan for each stage of the crop cycle."""

    from .growth_stage import list_growth_stages, get_stage_duration

    cycle_plan: Dict[str, Dict[int, Dict[str, float]]] = {}
    for stage in list_growth_stages(plant_type):
        days = get_stage_duration(plant_type, stage)
        if not days:
            continue
        cycle_plan[stage] = generate_fertigation_plan(
            plant_type,
            stage,
            days,
            purity,
            product=product,
        )
    return cycle_plan


def generate_cycle_fertigation_plan_with_cost(
    plant_type: str,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> tuple[Dict[str, Dict[int, Dict[str, float]]], float]:
    """Return cycle fertigation plan and estimated total cost."""

    plan = generate_cycle_fertigation_plan(plant_type, purity, product=product)

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
    )

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }

    totals: Dict[str, float] = {}
    for stage_plan in plan.values():
        for day_schedule in stage_plan.values():
            for nutrient, grams in day_schedule.items():
                fert = fert_map.get(nutrient)
                if fert:
                    totals[fert] = totals.get(fert, 0.0) + grams

    total = 0.0
    if totals:
        try:
            total = estimate_mix_cost(totals)
        except KeyError:
            total = 0.0

    return plan, round(total, 2)


def recommend_stock_solution_injection(
    targets: Mapping[str, float], volume_l: float
) -> Dict[str, float]:
    """Return stock solution volumes (mL) for the given nutrient targets."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    volumes: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        solution = _NUTRIENT_STOCK_MAP.get(nutrient)
        if not solution:
            continue
        conc = _STOCK_SOLUTIONS[solution].get(nutrient, 0.0)
        if conc <= 0:
            continue
        ml = ppm * volume_l / conc
        volumes[solution] = round(volumes.get(solution, 0.0) + ml, 2)

    return volumes


def validate_fertigation_schedule(
    schedule: Mapping[str, float], volume_l: float, plant_type: str
) -> Dict[str, Dict[str, float]]:
    """Return nutrient ppm, imbalance and toxicity diagnostics for ``schedule``.

    Parameters
    ----------
    schedule : Mapping[str, float]
        Fertilizer mix mapping product IDs to grams.
    volume_l : float
        Final solution volume in liters.
    plant_type : str
        Crop type used to check toxicity thresholds.
    """

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        calculate_mix_ppm,
    )

    ppm_levels = calculate_mix_ppm(schedule, volume_l)
    return {
        "ppm": ppm_levels,
        "imbalances": check_imbalances(ppm_levels),
        "toxicities": check_toxicities(ppm_levels, plant_type),
    }


def summarize_fertigation_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
    fertilizers: Mapping[str, str] | None = None,
) -> Dict[str, object]:
    """Return fertigation schedule with cost and solubility diagnostics.

    Parameters
    ----------
    plant_type : str
        Crop type name used for guideline lookup.
    stage : str
        Growth stage for guideline lookup.
    volume_l : float
        Total solution volume in liters.
    purity : Mapping[str, float] | None, optional
        Explicit nutrient purity overrides.
    product : str, optional
        Fertilizer product ID to load purity data from.
    fertilizers : Mapping[str, str] | None, optional
        Mapping of nutrient codes to fertilizer product IDs used for cost
        estimates.

    Returns
    -------
    Dict[str, object]
        Mapping with keys ``schedule``, ``cost_total``, ``cost_breakdown``
        and ``solubility_warnings``.
    """

    schedule = recommend_fertigation_schedule(
        plant_type,
        stage,
        volume_l,
        purity,
        product=product,
    )

    if fertilizers:
        from plant_engine.fertigation import recommend_nutrient_mix_with_cost_breakdown

        _, total, breakdown = recommend_nutrient_mix_with_cost_breakdown(
            plant_type,
            stage,
            volume_l,
            fertilizers=fertilizers,
            purity_overrides=purity,
        )
    else:
        total = 0.0
        breakdown = {}
    warnings = check_solubility_limits(schedule, volume_l)

    return {
        "schedule": schedule,
        "cost_total": total,
        "cost_breakdown": breakdown,
        "solubility_warnings": warnings,
    }
