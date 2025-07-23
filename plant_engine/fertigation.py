"""Utility functions for fertigation calculations."""
from __future__ import annotations

from functools import lru_cache
from datetime import date, timedelta
from typing import Dict, Mapping, Iterable

from .nutrient_manager import (
    calculate_deficiencies,
    get_recommended_levels,
    calculate_all_deficiencies,
    get_all_recommended_levels,
)
from .utils import load_dataset, normalize_key

FOLIAR_DATA = "foliar_feed_guidelines.json"
INTERVAL_DATA = "foliar_feed_intervals.json"
FERTIGATION_INTERVAL_DATA = "fertigation_intervals.json"

PURITY_DATA = "fertilizer_purity.json"
EC_FACTOR_DATA = "ion_ec_factors.json"

_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(INTERVAL_DATA)
_FERTIGATION_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(FERTIGATION_INTERVAL_DATA)


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

    data = _INTERVALS.get(normalize_key(plant_type), {})
    if stage:
        value = data.get(normalize_key(stage))
        if isinstance(value, (int, float)):
            return int(value)
    value = data.get("optimal")
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
def get_fertigation_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between fertigation events."""

    data = _FERTIGATION_INTERVALS.get(normalize_key(plant_type), {})
    if stage:
        value = data.get(normalize_key(stage))
        if isinstance(value, (int, float)):
            return int(value)
    value = data.get("optimal")
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
    "get_foliar_guidelines",
    "recommend_foliar_feed",
    "get_foliar_feed_interval",
    "next_foliar_feed_date",
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
    "generate_fertigation_plan",
    "calculate_mix_nutrients",
    "estimate_solution_ec",
    "estimate_stage_cost",
    "estimate_cycle_cost",
    "generate_cycle_fertigation_plan",
    "generate_cycle_fertigation_plan_with_cost",
    "recommend_precise_fertigation",
    "grams_to_ppm",
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
        schedule[nutrient] = _ppm_to_grams(
            ppm, volume_l, purity_map.get(nutrient, 1.0)
        )
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

    if include_micro:
        if current_levels is None:
            deficits = get_all_recommended_levels(plant_type, stage)
        else:
            deficits = calculate_all_deficiencies(current_levels, plant_type, stage)
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
) -> tuple[Dict[str, float], float, Dict[str, float], Dict[str, Dict[str, float]]]:
    """Return fertigation schedule with cost and optional water adjustments."""

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
        )
        warnings = {}

    from custom_components.horticulture_assistant.fertilizer_formulator import (
        estimate_mix_cost,
        estimate_cost_breakdown,
    )

    total = estimate_mix_cost(schedule)
    breakdown = estimate_cost_breakdown(schedule)

    return schedule, total, breakdown, warnings


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

    schedule = _schedule_from_totals(
        totals, num_plants, fertilizers, purity_overrides
    )
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

    schedule = _schedule_from_totals(
        totals, num_plants, fertilizers, purity_overrides
    )
    return estimate_mix_cost(schedule)


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

    plan = generate_cycle_fertigation_plan(
        plant_type, purity, product=product
    )

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



