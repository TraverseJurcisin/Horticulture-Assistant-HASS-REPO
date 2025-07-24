"""Helpers for irrigation scheduling."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping, Dict, Any

from .utils import load_dataset, normalize_key
from .et_model import calculate_eta

from .rootzone_model import RootZone, calculate_remaining_water

__all__ = [
    "recommend_irrigation_volume",
    "recommend_irrigation_with_rainfall",
    "recommend_irrigation_interval",
    "get_crop_coefficient",
    "estimate_irrigation_demand",
    "estimate_irrigation_from_month",
    "recommend_irrigation_from_environment",
    "list_supported_plants",
    "get_daily_irrigation_target",
    "generate_irrigation_schedule",
    "generate_irrigation_schedule_with_runtime",
    "adjust_irrigation_for_efficiency",
    "generate_env_irrigation_schedule",
    "generate_precipitation_schedule",
    "get_rain_capture_efficiency",
    "get_recommended_interval",
    "estimate_irrigation_time",
    "IrrigationRecommendation",
    "get_water_price",
    "estimate_irrigation_cost",
    "estimate_schedule_cost",
]

_KC_DATA_FILE = "crop_coefficients.json"
_KC_DATA = load_dataset(_KC_DATA_FILE)

_IRRIGATION_FILE = "irrigation_guidelines.json"
_IRRIGATION_DATA: Dict[str, Dict[str, float]] = load_dataset(_IRRIGATION_FILE)

_INTERVAL_FILE = "irrigation_intervals.json"
_INTERVAL_DATA: Dict[str, Dict[str, float]] = load_dataset(_INTERVAL_FILE)

_EFFICIENCY_FILE = "irrigation_efficiency.json"
_EFFICIENCY_DATA: Dict[str, float] = load_dataset(_EFFICIENCY_FILE)

_FLOW_FILE = "emitter_flow_rates.json"
_FLOW_DATA: Dict[str, float] = load_dataset(_FLOW_FILE)

_RAIN_EFFICIENCY_FILE = "rain_capture_efficiency.json"
_RAIN_EFFICIENCY_DATA: Dict[str, float] = load_dataset(_RAIN_EFFICIENCY_FILE)

_WATER_PRICE_FILE = "water_prices.json"
_WATER_PRICE_DATA: Dict[str, float] = load_dataset(_WATER_PRICE_FILE)


@dataclass(frozen=True)
class IrrigationRecommendation:
    """Recommended irrigation volume with ET metrics."""

    volume_ml: float
    metrics: Mapping[str, float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "volume_ml": self.volume_ml,
            "metrics": dict(self.metrics),
        }


def recommend_irrigation_volume(
    rootzone: RootZone,
    available_ml: float,
    expected_et_ml: float,
    *,
    refill_to_full: bool = True,
) -> float:
    """Return irrigation volume needed to maintain root zone moisture.

    Parameters
    ----------
    rootzone : RootZone
        Water holding model for the plant.
    available_ml : float
        Current available water volume in milliliters.
    expected_et_ml : float
        Expected evapotranspiration loss before next irrigation.
    refill_to_full : bool, optional
        When ``True`` the zone is filled back to field capacity; otherwise only
        enough water to reach the readily available level is recommended.
    """
    if expected_et_ml < 0:
        raise ValueError("expected_et_ml must be non-negative")
    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

    projected = available_ml - expected_et_ml
    if projected >= rootzone.readily_available_water_ml:
        return 0.0

    target = rootzone.total_available_water_ml if refill_to_full else rootzone.readily_available_water_ml
    required = target - projected
    max_add = rootzone.total_available_water_ml - available_ml
    required = min(required, max_add)
    return round(max(required, 0.0), 1)


def recommend_irrigation_with_rainfall(
    rootzone: RootZone,
    available_ml: float,
    expected_et_ml: float,
    rainfall_ml: float,
    *,
    refill_to_full: bool = True,
    runoff_fraction: float = 0.1,
) -> float:
    """Return irrigation volume adjusted for expected rainfall.

    ``rainfall_ml`` represents precipitation reaching the soil. A portion may
    be lost to runoff or interception, controlled by ``runoff_fraction``.
    The remaining water offsets evapotranspiration loss before calculating the
    required irrigation volume via :func:`recommend_irrigation_volume`.
    """

    if rainfall_ml < 0:
        raise ValueError("rainfall_ml must be non-negative")
    if not 0 <= runoff_fraction <= 1:
        raise ValueError("runoff_fraction must be between 0 and 1")

    net_rain = rainfall_ml * (1 - runoff_fraction)
    adjusted_et = max(expected_et_ml - net_rain, 0.0)
    return recommend_irrigation_volume(
        rootzone,
        available_ml,
        adjusted_et,
        refill_to_full=refill_to_full,
    )


def recommend_irrigation_interval(
    rootzone: RootZone,
    available_ml: float,
    expected_et_ml_day: float,
) -> float:
    """Return days until irrigation is required based on ET rate.

    ``available_ml`` is the current water volume in the root zone. The function
    estimates how many days of evapotranspiration it will take for the soil
    moisture to drop to the readily available level. ``expected_et_ml_day`` must
    be positive.
    """

    if expected_et_ml_day <= 0:
        raise ValueError("expected_et_ml_day must be positive")
    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

    depletion = available_ml - rootzone.readily_available_water_ml
    if depletion <= 0:
        return 0.0

    days = depletion / expected_et_ml_day
    return round(max(days, 0.0), 2)


def get_crop_coefficient(plant_type: str, stage: str) -> float:
    """Return crop coefficient for ``plant_type`` and ``stage``."""
    coeffs = _KC_DATA.get(normalize_key(plant_type), {})
    return coeffs.get(normalize_key(stage), 1.0)


def estimate_irrigation_demand(
    plant_type: str,
    stage: str,
    et0_mm_day: float,
    area_m2: float = 1.0,
) -> float:
    """Return daily irrigation volume in liters.

    Parameters
    ----------
    plant_type : str
        Plant type used to look up the crop coefficient.
    stage : str
        Growth stage for the coefficient lookup.
    et0_mm_day : float
        Reference ET in millimeters per day.
    area_m2 : float, optional
        Plant canopy area in square meters. 1 mm over 1 m² equals 1 L.
    """
    if et0_mm_day < 0:
        raise ValueError("et0_mm_day must be non-negative")
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")

    kc = get_crop_coefficient(plant_type, stage)
    eta_mm = calculate_eta(et0_mm_day, kc)
    liters = eta_mm * area_m2
    return round(liters, 2)


def estimate_irrigation_from_month(
    plant_type: str,
    stage: str,
    month: int,
    area_m2: float = 1.0,
) -> float:
    """Return irrigation demand using monthly reference ET₀."""

    from .et_model import get_reference_et0

    et0 = get_reference_et0(month)
    if et0 is None:
        return 0.0
    return estimate_irrigation_demand(plant_type, stage, et0, area_m2)


def adjust_irrigation_for_efficiency(volume_ml: float, method: str) -> float:
    """Return volume adjusted for irrigation system efficiency.

    ``method`` is matched against :data:`irrigation_efficiency.json`.
    The stored value represents the fraction of water that actually
    reaches the root zone. If the method is unknown or invalid the
    input volume is returned unchanged.
    """

    if volume_ml < 0:
        raise ValueError("volume_ml must be non-negative")

    eff = _EFFICIENCY_DATA.get(normalize_key(method))
    if isinstance(eff, (int, float)) and 0 < eff <= 1:
        return round(volume_ml / eff, 1)
    return volume_ml


def estimate_irrigation_time(
    volume_ml: float, emitter_type: str, emitters: int = 1
) -> float:
    """Return hours required to apply ``volume_ml`` with ``emitter_type``.

    Flow rates are loaded from :data:`emitter_flow_rates.json` in liters per
    hour for a single emitter. ``emitters`` specifies how many emitters are
    used simultaneously. ``0.0`` is returned when the emitter type is unknown.
    ``volume_ml`` and ``emitters`` must be positive.
    """

    if volume_ml <= 0:
        raise ValueError("volume_ml must be positive")
    if emitters <= 0:
        raise ValueError("emitters must be positive")

    rate_l_h = _FLOW_DATA.get(normalize_key(emitter_type))
    if not isinstance(rate_l_h, (int, float)) or rate_l_h <= 0:
        return 0.0

    rate_ml_h = rate_l_h * 1000 * emitters
    hours = volume_ml / rate_ml_h
    return round(hours, 2)


def get_rain_capture_efficiency(surface: str) -> float:
    """Return fraction of rainfall captured for ``surface``."""
    value = _RAIN_EFFICIENCY_DATA.get(normalize_key(surface), 1.0)
    try:
        eff = float(value)
    except (TypeError, ValueError):
        eff = 1.0
    return max(0.0, min(eff, 1.0))


def recommend_irrigation_from_environment(
    plant_profile: Mapping[str, float],
    env_data: Mapping[str, float],
    rootzone: RootZone,
    available_ml: float,
    *,
    refill_to_full: bool = True,
) -> Dict[str, object]:
    """Return irrigation recommendation using environment readings."""

    from .compute_transpiration import compute_transpiration

    metrics = compute_transpiration(plant_profile, env_data)
    volume = recommend_irrigation_volume(
        rootzone,
        available_ml,
        metrics["transpiration_ml_day"],
        refill_to_full=refill_to_full,
    )

    rec = IrrigationRecommendation(volume_ml=volume, metrics=metrics)
    return rec.as_dict()


def list_supported_plants() -> list[str]:
    """Return plant types with irrigation guidelines."""

    return sorted(_IRRIGATION_DATA.keys())


def get_daily_irrigation_target(plant_type: str, stage: str) -> float:
    """Return recommended daily irrigation volume in milliliters."""

    plant = _IRRIGATION_DATA.get(normalize_key(plant_type), {})
    value = plant.get(normalize_key(stage))
    return float(value) if isinstance(value, (int, float)) else 0.0


def get_recommended_interval(plant_type: str, stage: str) -> float | None:
    """Return days between irrigation events for a plant stage if known."""

    plant = _INTERVAL_DATA.get(normalize_key(plant_type), {})
    value = plant.get(normalize_key(stage))
    if isinstance(value, (int, float)):
        return float(value)
    value = plant.get("optimal")
    return float(value) if isinstance(value, (int, float)) else None


def generate_irrigation_schedule(
    rootzone: RootZone,
    available_ml: float,
    et_ml_series: Mapping[int, float] | list[float],
    *,
    refill_to_full: bool = True,
    method: str | None = None,
) -> Dict[int, float]:
    """Return daily irrigation volumes to maintain root zone moisture.

    If ``method`` is provided the returned volumes are adjusted for the
    irrigation efficiency defined in :data:`irrigation_efficiency.json`.

    ``et_ml_series`` should contain expected evapotranspiration loss for each
    day in milliliters. The function simulates soil moisture over the period and
    calls :func:`recommend_irrigation_volume` for each day, accounting for
    irrigation applied on previous days.
    """

    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")
    if any(v < 0 for v in et_ml_series):
        raise ValueError("et_ml_series values must be non-negative")

    schedule: Dict[int, float] = {}
    remaining = float(available_ml)
    for day, et_ml in enumerate(et_ml_series, start=1):
        volume = recommend_irrigation_volume(
            rootzone, remaining, et_ml, refill_to_full=refill_to_full
        )
        if method:
            volume = adjust_irrigation_for_efficiency(volume, method)
        schedule[day] = volume
        remaining = calculate_remaining_water(
            rootzone, remaining, irrigation_ml=volume, et_ml=et_ml
        )

    return schedule


def generate_env_irrigation_schedule(
    plant_profile: Mapping[str, float],
    env_series: Iterable[Mapping[str, float]],
    rootzone: RootZone,
    available_ml: float,
    *,
    refill_to_full: bool = True,
    method: str | None = None,
) -> Dict[int, Dict[str, object]]:
    """Return irrigation schedule using daily environment readings."""

    from .compute_transpiration import compute_transpiration

    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

    schedule: Dict[int, Dict[str, object]] = {}
    remaining = float(available_ml)

    for day, env in enumerate(env_series, start=1):
        metrics = compute_transpiration(plant_profile, env)
        et_ml = metrics["transpiration_ml_day"]
        volume = recommend_irrigation_volume(
            rootzone, remaining, et_ml, refill_to_full=refill_to_full
        )
        if method:
            volume = adjust_irrigation_for_efficiency(volume, method)
        schedule[day] = {"volume_ml": volume, "metrics": metrics}
        remaining = calculate_remaining_water(
            rootzone, remaining, irrigation_ml=volume, et_ml=et_ml
        )

    return schedule


def generate_precipitation_schedule(
    rootzone: RootZone,
    available_ml: float,
    et_ml_series: Iterable[float],
    precipitation_ml: Iterable[float],
    *,
    refill_to_full: bool = True,
    method: str | None = None,
    surface: str = "bare_soil",
) -> Dict[int, float]:
    """Return irrigation schedule adjusted for rainfall."""

    if available_ml < 0:
        raise ValueError("available_ml must be non-negative")

    rain_eff = get_rain_capture_efficiency(surface)
    schedule: Dict[int, float] = {}
    remaining = float(available_ml)

    for day, (et_ml, rain_ml) in enumerate(zip(et_ml_series, precipitation_ml), start=1):
        net_et = max(0.0, et_ml - rain_ml * rain_eff)
        volume = recommend_irrigation_volume(
            rootzone, remaining, net_et, refill_to_full=refill_to_full
        )
        if method:
            volume = adjust_irrigation_for_efficiency(volume, method)
        schedule[day] = volume
        remaining = calculate_remaining_water(
            rootzone, remaining, irrigation_ml=volume, et_ml=net_et
        )

    return schedule


def generate_irrigation_schedule_with_runtime(
    rootzone: RootZone,
    available_ml: float,
    et_ml_series: Mapping[int, float] | list[float],
    *,
    refill_to_full: bool = True,
    method: str | None = None,
    emitter_type: str | None = None,
    emitters: int = 1,
) -> Dict[int, Dict[str, float | None]]:
    """Return daily irrigation volumes and runtime estimates."""

    schedule = generate_irrigation_schedule(
        rootzone,
        available_ml,
        et_ml_series,
        refill_to_full=refill_to_full,
        method=method,
    )

    result: Dict[int, Dict[str, float | None]] = {}
    for day, volume in schedule.items():
        if emitter_type and volume > 0:
            runtime = estimate_irrigation_time(volume, emitter_type, emitters)
        else:
            runtime = None
        result[day] = {"volume_ml": volume, "runtime_h": runtime}

    return result


def get_water_price(source: str) -> float:
    """Return cost per liter for a water ``source``."""

    return float(_WATER_PRICE_DATA.get(normalize_key(source), 0.0))


def estimate_irrigation_cost(volume_ml: float, source: str = "municipal") -> float:
    """Return estimated cost for ``volume_ml`` of irrigation water."""

    if volume_ml < 0:
        raise ValueError("volume_ml must be non-negative")
    price = get_water_price(source)
    return round(price * (volume_ml / 1000), 4)


def estimate_schedule_cost(schedule: Mapping[int, float], source: str = "municipal") -> float:
    """Return total water cost for an irrigation ``schedule``."""

    total_ml = sum(max(v, 0.0) for v in schedule.values())
    return estimate_irrigation_cost(total_ml, source)
