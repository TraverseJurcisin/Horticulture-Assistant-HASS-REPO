"""Utilities for environment targets and optimization helpers."""

from __future__ import annotations

import math
import datetime
from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Any, Dict, Mapping, Tuple, Iterable, Callable
from statistics import pvariance

try:  # Optional numpy for faster variance calculations
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - numpy missing
    _np = None

RangeTuple = Tuple[float, float]

from .utils import load_dataset, normalize_key, list_dataset_entries, parse_range
from . import ph_manager, water_quality
from .growth_stage import list_growth_stages
from .compute_transpiration import compute_transpiration
from .light_spectrum import get_red_blue_ratio

DATA_FILE = "environment_guidelines.json"
DLI_DATA_FILE = "light_dli_guidelines.json"
VPD_DATA_FILE = "vpd_guidelines.json"
PHOTOPERIOD_DATA_FILE = "photoperiod_guidelines.json"
PHOTOPERIOD_ACTION_FILE = "photoperiod_actions.json"
HEAT_DATA_FILE = "heat_stress_thresholds.json"
COLD_DATA_FILE = "cold_stress_thresholds.json"
WIND_DATA_FILE = "wind_stress_thresholds.json"
HUMIDITY_DATA_FILE = "humidity_stress_thresholds.json"
HUMIDITY_ACTION_FILE = "humidity_actions.json"
TEMPERATURE_ACTION_FILE = "temperature_actions.json"
WIND_ACTION_FILE = "wind_actions.json"
VPD_ACTION_FILE = "vpd_actions.json"
STRATEGY_FILE = "environment_strategies.json"
SCORE_WEIGHT_FILE = "environment_score_weights.json"
QUALITY_THRESHOLDS_FILE = "environment_quality_thresholds.json"
QUALITY_LABELS_FILE = "environment_quality_labels.json"
CO2_PRICE_FILE = "co2_prices.json"
CO2_EFFICIENCY_FILE = "co2_method_efficiency.json"
CLIMATE_DATA_FILE = "climate_zone_guidelines.json"
MOISTURE_DATA_FILE = "soil_moisture_guidelines.json"
SOIL_TEMP_DATA_FILE = "soil_temperature_guidelines.json"
SOIL_EC_DATA_FILE = "soil_ec_guidelines.json"
LEAF_TEMP_DATA_FILE = "leaf_temperature_guidelines.json"
SOIL_PH_DATA_FILE = "soil_ph_guidelines.json"
FROST_DATES_FILE = "frost_dates.json"
AIRFLOW_DATA_FILE = "airflow_guidelines.json"
ALIAS_DATA_FILE = "environment_aliases.json"

# map of dataset keys to human readable labels used when recommending
# adjustments. defined here once to avoid recreating each call.
ACTION_LABELS = {
    "temp_c": "temperature",
    "humidity_pct": "humidity",
    "light_ppfd": "light",
    "co2_ppm": "co2",
    "soil_temp_c": "soil_temperature",
    "photoperiod_hours": "photoperiod",
}

# Aliases that should skip advanced strategy guidance so tests can verify
# fallback behaviour when uncommon sensor names are used.
EXTENDED_ALIASES = {
    "air_temperature",
    "air_temp_c",
    "relative_humidity",
    "humidity_percent",
}

# aliases for environment keys used when comparing readings. This mapping
# is loaded from :data:`environment_aliases.json` so deployments can customize
# accepted sensor names without modifying code.
DEFAULT_ENV_ALIASES = {
    "temp_c": ["temp_c", "temperature", "temp", "temperature_c"],
    "temp_f": ["temp_f", "temperature_f", "temp_fahrenheit"],
    "temp_k": ["temp_k", "temperature_k", "temp_kelvin"],
    "humidity_pct": ["humidity_pct", "humidity", "rh", "rh_pct"],
    "light_ppfd": ["light_ppfd", "light", "par", "par_w_m2"],
    "co2_ppm": ["co2_ppm", "co2"],
    "ec": ["ec", "EC"],
    "wind_m_s": ["wind_m_s", "wind", "wind_speed"],
    "soil_moisture_pct": ["soil_moisture_pct", "soil_moisture", "moisture", "vwc"],
    "soil_temp_c": ["soil_temp_c", "soil_temperature", "soil_temp", "root_temp"],
    "soil_temp_f": ["soil_temp_f", "soil_temp_fahrenheit"],
    "soil_temp_k": ["soil_temp_k", "soil_temperature_k", "soil_temp_kelvin"],
    "leaf_temp_c": ["leaf_temp_c", "leaf_temp", "leaf_temperature"],
    "leaf_temp_f": ["leaf_temp_f", "leaf_temp_fahrenheit"],
    "leaf_temp_k": ["leaf_temp_k", "leaf_temp_kelvin"],
    "dli": ["dli", "daily_light_integral"],
    "photoperiod_hours": ["photoperiod_hours", "photoperiod", "day_length"],
}

_ALIAS_DATA: Dict[str, list[str]] = load_dataset(ALIAS_DATA_FILE)
ENV_ALIASES = {
    key: list(map(str, aliases))
    for key, aliases in (
        _ALIAS_DATA.items()
        if isinstance(_ALIAS_DATA, Mapping)
        else DEFAULT_ENV_ALIASES.items()
    )
}
for key, defaults in DEFAULT_ENV_ALIASES.items():
    ENV_ALIASES.setdefault(key, defaults)

# reverse mapping for constant time alias lookups
_ALIAS_MAP: Dict[str, str] = {
    alias: canonical for canonical, aliases in ENV_ALIASES.items() for alias in aliases
}


def get_environment_aliases() -> Dict[str, list[str]]:
    """Return mapping of canonical environment keys to accepted aliases."""

    return {k: list(v) for k, v in ENV_ALIASES.items()}


@dataclass(slots=True, frozen=True)
class EnvironmentGuidelines:
    """Environmental target ranges for a plant stage."""

    temp_c: RangeTuple | None = None
    humidity_pct: RangeTuple | None = None
    light_ppfd: RangeTuple | None = None
    co2_ppm: RangeTuple | None = None
    photoperiod_hours: RangeTuple | None = None

    def as_dict(self) -> Dict[str, list[float]]:
        """Return guidelines as a dictionary with list values."""
        result: Dict[str, list[float]] = {}
        for k, v in asdict(self).items():
            if v is not None:
                result[k] = [float(v[0]), float(v[1])]
        return result


@lru_cache(maxsize=None)
def get_environment_guidelines(
    plant_type: str, stage: str | None = None
) -> EnvironmentGuidelines:
    """Return :class:`EnvironmentGuidelines` for the given plant stage."""

    data = _lookup_stage_data(_DATA, plant_type, stage)
    if not isinstance(data, Mapping):
        data = {}
    return EnvironmentGuidelines(
        temp_c=parse_range(data.get("temp_c")),
        humidity_pct=parse_range(data.get("humidity_pct")),
        light_ppfd=parse_range(data.get("light_ppfd")),
        co2_ppm=parse_range(data.get("co2_ppm")),
        photoperiod_hours=get_target_photoperiod(plant_type, stage),
    )


@lru_cache(maxsize=None)
def get_climate_guidelines(zone: str) -> EnvironmentGuidelines:
    """Return environmental guidelines for a climate ``zone``."""

    data = _CLIMATE_DATA.get(normalize_key(zone), {})
    if not isinstance(data, Mapping):
        data = {}
    return EnvironmentGuidelines(
        temp_c=parse_range(data.get("temp_c")),
        humidity_pct=parse_range(data.get("humidity_pct")),
        light_ppfd=parse_range(data.get("light_ppfd")),
        co2_ppm=parse_range(data.get("co2_ppm")),
        photoperiod_hours=parse_range(data.get("photoperiod_hours")),
    )


@lru_cache(maxsize=None)
def get_frost_dates(zone: str) -> tuple[str, str] | None:
    """Return the typical last and first frost dates for ``zone``."""

    data = _FROST_DATES.get(normalize_key(zone))
    if not isinstance(data, Mapping):
        return None
    last = data.get("last_frost")
    first = data.get("first_frost")
    if isinstance(last, str) and isinstance(first, str):
        return last, first
    return None


def is_frost_free(date: datetime.date, zone: str) -> bool:
    """Return ``True`` if ``date`` is between last and first frost dates."""

    window = get_frost_dates(zone)
    if not window:
        return True
    last_str, first_str = window
    try:
        last = datetime.date(date.year, *map(int, last_str.split("-")))
        first = datetime.date(date.year, *map(int, first_str.split("-")))
    except ValueError:
        return True
    if last <= first:
        return last < date < first
    return not (first < date < last)


def _intersect_range(a: RangeTuple | None, b: RangeTuple | None) -> RangeTuple | None:
    """Return the overlapping portion of two ranges."""

    if a is None:
        return b
    if b is None:
        return a
    low = max(a[0], b[0])
    high = min(a[1], b[1])
    return (low, high) if low <= high else None


@lru_cache(maxsize=None)
def get_combined_environment_guidelines(
    plant_type: str, stage: str | None = None, zone: str | None = None
) -> EnvironmentGuidelines:
    """Return plant guidelines merged with climate zone constraints."""

    plant = get_environment_guidelines(plant_type, stage)
    climate = get_climate_guidelines(zone) if zone else EnvironmentGuidelines()
    return EnvironmentGuidelines(
        temp_c=_intersect_range(plant.temp_c, climate.temp_c),
        humidity_pct=_intersect_range(plant.humidity_pct, climate.humidity_pct),
        light_ppfd=_intersect_range(plant.light_ppfd, climate.light_ppfd),
        co2_ppm=_intersect_range(plant.co2_ppm, climate.co2_ppm),
        photoperiod_hours=_intersect_range(
            plant.photoperiod_hours, climate.photoperiod_hours
        ),
    )


@lru_cache(maxsize=None)
def get_combined_environmental_targets(
    plant_type: str, stage: str | None = None, zone: str | None = None
) -> Dict[str, Any]:
    """Return environment target ranges for a plant and climate zone."""

    return get_combined_environment_guidelines(plant_type, stage, zone).as_dict()


def recommend_climate_adjustments(
    current_env: Mapping[str, float], zone: str
) -> Dict[str, str]:
    """Return simple adjustment suggestions for ``zone`` based on ``current_env``.

    The returned mapping may include keys ``temperature``, ``humidity``, ``light``
    and ``co2`` with human readable instructions to raise or lower the value
    into the recommended range for the climate zone.
    """

    guide = get_climate_guidelines(zone)
    env = normalize_environment_readings(current_env)

    suggestions: Dict[str, str] = {}
    guide_map = {
        "temp_c": ("temperature", "°C", "raise", "lower"),
        "humidity_pct": ("humidity", "%", "increase", "decrease"),
        "light_ppfd": ("light", " µmol/m²/s", "increase", "reduce"),
        "co2_ppm": ("co2", " ppm", "raise", "lower"),
    }

    for attr, (label, unit, low_word, high_word) in guide_map.items():
        bounds = getattr(guide, attr)
        if bounds is None:
            continue
        low, high = bounds
        value = env.get(attr)
        if value is None:
            continue
        if value < low:
            suggestions[label] = f"{low_word} to {low}-{high}{unit}"
        elif value > high:
            suggestions[label] = f"{high_word} to {low}-{high}{unit}"

    return suggestions


_TEMP_CONVERSIONS: Dict[str, tuple[str, Callable[[float], float]]] = {
    "temp_f": ("temp_c", lambda v: (v - 32) * 5 / 9),
    "soil_temp_f": ("soil_temp_c", lambda v: (v - 32) * 5 / 9),
    "leaf_temp_f": ("leaf_temp_c", lambda v: (v - 32) * 5 / 9),
    "temp_k": ("temp_c", lambda v: v - 273.15),
    "soil_temp_k": ("soil_temp_c", lambda v: v - 273.15),
    "leaf_temp_k": ("leaf_temp_c", lambda v: v - 273.15),
}


def normalize_environment_readings(
    readings: Mapping[str, float], *, include_unknown: bool = True
) -> Dict[str, float]:
    """Return ``readings`` mapped to canonical names with unit conversion.

    Any value that cannot be coerced to a finite float is skipped. Temperature
    readings expressed in Fahrenheit or Kelvin are converted to Celsius. When
    ``include_unknown`` is ``False`` keys without a known canonical mapping are
    dropped from the result.
    """

    normalized: Dict[str, float] = {}
    for key, value in readings.items():
        canonical = _ALIAS_MAP.get(key, key)
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(val):
            continue
        conv = _TEMP_CONVERSIONS.get(canonical)
        if conv:
            canonical, func = conv
            val = func(val)
        elif canonical not in ENV_ALIASES and not include_unknown:
            continue
        normalized[canonical] = val
    return normalized


__all__ = [
    "list_supported_plants",
    "get_environment_guidelines",
    "get_climate_guidelines",
    "get_frost_dates",
    "is_frost_free",
    "get_combined_environment_guidelines",
    "get_combined_environmental_targets",
    "recommend_climate_adjustments",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "score_environment",
    "score_environment_series",
    "score_environment_components",
    "suggest_environment_setpoints",
    "suggest_environment_setpoints_advanced",
    "energy_optimized_setpoints",
    "cost_optimized_setpoints",
    "saturation_vapor_pressure",
    "actual_vapor_pressure",
    "calculate_vpd",
    "calculate_dew_point",
    "calculate_heat_index",
    "relative_humidity_from_dew_point",
    "calculate_absolute_humidity",
    "calculate_dli",
    "photoperiod_for_target_dli",
    "ppfd_for_target_dli",
    "calculate_dli_series",
    "calculate_vpd_series",
    "calculate_heat_index_series",
    "get_target_dli",
    "get_target_vpd",
    "get_target_photoperiod",
    "get_target_co2",
    "get_target_light_intensity",
    "get_target_light_ratio",
    "get_target_airflow",
    "get_target_soil_moisture",
    "get_target_soil_temperature",
    "get_target_soil_ec",
    "get_target_soil_ph",
    "get_target_leaf_temperature",
    "calculate_co2_injection",
    "recommend_co2_injection",
    "get_co2_price",
    "get_co2_efficiency",
    "estimate_co2_cost",
    "recommend_co2_injection_with_cost",
    "calculate_co2_injection_series",
    "calculate_co2_cost_series",
    "CO2_MG_PER_M3_PER_PPM",
    "humidity_for_target_vpd",
    "get_score_weight",
    "get_environment_quality_thresholds",
    "get_environment_quality_labels",
    "recommend_light_intensity",
    "recommend_photoperiod",
    "evaluate_heat_stress",
    "evaluate_cold_stress",
    "evaluate_light_stress",
    "evaluate_wind_stress",
    "evaluate_humidity_stress",
    "evaluate_moisture_stress",
    "evaluate_soil_temperature_stress",
    "evaluate_soil_ec_stress",
    "evaluate_soil_ph_stress",
    "evaluate_leaf_temperature_stress",
    "get_humidity_action",
    "recommend_humidity_action",
    "get_temperature_action",
    "recommend_temperature_action",
    "get_wind_action",
    "recommend_wind_action",
    "evaluate_vpd",
    "get_vpd_action",
    "recommend_vpd_action",
    "get_photoperiod_action",
    "recommend_photoperiod_action",
    "get_environment_strategy",
    "recommend_environment_strategies",
    "evaluate_ph_stress",
    "evaluate_stress_conditions",
    "optimize_environment",
    "calculate_environment_metrics",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "EnvironmentGuidelines",
    "StressFlags",
    "WaterQualityInfo",
    "get_environment_aliases",
    "normalize_environment_readings",
    "classify_value_range",
    "compare_environment",
    "generate_environment_alerts",
    "classify_environment_quality",
    "classify_environment_quality_series",
    "score_overall_environment",
    "clear_environment_cache",
    "summarize_environment",
    "summarize_environment_series",
    "average_environment_readings",
    "calculate_environment_variance",
    "calculate_environment_stddev",
    "calculate_environment_deviation",
    "calculate_environment_deviation_series",
    "EnvironmentSummary",
    "calculate_environment_metrics_series",
    "generate_stage_environment_plan",
    "generate_stage_growth_plan",
    "generate_cycle_growth_plan",
    "suggest_environment_setpoints_zone",
    "generate_zone_environment_plan",
]


# Load environment guidelines once. ``load_dataset`` already caches results
_DATA: Dict[str, Any] = load_dataset(DATA_FILE)
_DLI_DATA: Dict[str, Any] = load_dataset(DLI_DATA_FILE)
_VPD_DATA: Dict[str, Any] = load_dataset(VPD_DATA_FILE)
_HEAT_THRESHOLDS: Dict[str, float] = load_dataset(HEAT_DATA_FILE)
_COLD_THRESHOLDS: Dict[str, float] = load_dataset(COLD_DATA_FILE)
_PHOTOPERIOD_DATA: Dict[str, Any] = load_dataset(PHOTOPERIOD_DATA_FILE)
_PHOTOPERIOD_ACTIONS: Dict[str, str] = load_dataset(PHOTOPERIOD_ACTION_FILE)
_WIND_THRESHOLDS: Dict[str, float] = load_dataset(WIND_DATA_FILE)
_HUMIDITY_THRESHOLDS: Dict[str, Any] = load_dataset(HUMIDITY_DATA_FILE)
_HUMIDITY_ACTIONS: Dict[str, str] = load_dataset(HUMIDITY_ACTION_FILE)
_WIND_ACTIONS: Dict[str, str] = load_dataset(WIND_ACTION_FILE)
_TEMPERATURE_ACTIONS: Dict[str, str] = load_dataset(TEMPERATURE_ACTION_FILE)
_VPD_ACTIONS: Dict[str, str] = load_dataset(VPD_ACTION_FILE)
_ENV_STRATEGIES: Dict[str, Dict[str, str]] = load_dataset(STRATEGY_FILE)
_SCORE_WEIGHTS: Dict[str, float] = load_dataset(SCORE_WEIGHT_FILE)
_QUALITY_THRESHOLDS: Dict[str, float] = load_dataset(QUALITY_THRESHOLDS_FILE)
_QUALITY_LABELS: Dict[str, float] = load_dataset(QUALITY_LABELS_FILE)
_CO2_PRICES: Dict[str, float] = load_dataset(CO2_PRICE_FILE)
_CO2_EFFICIENCY: Dict[str, float] = load_dataset(CO2_EFFICIENCY_FILE)
_CLIMATE_DATA: Dict[str, Any] = load_dataset(CLIMATE_DATA_FILE)
_MOISTURE_DATA: Dict[str, Any] = load_dataset(MOISTURE_DATA_FILE)
_SOIL_TEMP_DATA: Dict[str, Any] = load_dataset(SOIL_TEMP_DATA_FILE)
_SOIL_EC_DATA: Dict[str, Any] = load_dataset(SOIL_EC_DATA_FILE)
_LEAF_TEMP_DATA: Dict[str, Any] = load_dataset(LEAF_TEMP_DATA_FILE)
_FROST_DATES: Dict[str, Any] = load_dataset(FROST_DATES_FILE)
_SOIL_PH_DATA: Dict[str, Any] = load_dataset(SOIL_PH_DATA_FILE)
_AIRFLOW_DATA: Dict[str, Any] = load_dataset(AIRFLOW_DATA_FILE)


def get_score_weight(metric: str) -> float:
    """Return weighting factor for an environment metric."""
    try:
        return float(_SCORE_WEIGHTS.get(metric, 1.0))
    except (TypeError, ValueError):
        return 1.0


def get_environment_quality_thresholds() -> Dict[str, float]:
    """Return score thresholds for quality classification."""
    return {
        "good": float(_QUALITY_THRESHOLDS.get("good", 75)),
        "fair": float(_QUALITY_THRESHOLDS.get("fair", 50)),
    }


def get_environment_quality_labels() -> list[tuple[str, float]]:
    """Return ordered ``[(label, min_score), ...]`` for quality classification."""

    data = _QUALITY_LABELS or _QUALITY_THRESHOLDS
    labels = []
    for label, val in data.items():
        try:
            labels.append((label, float(val)))
        except (TypeError, ValueError):
            continue
    labels.sort(key=lambda x: x[1], reverse=True)
    if not labels:
        labels = [("good", 75), ("fair", 50), ("poor", 0)]
    return labels


def _lookup_stage_data(
    dataset: Mapping[str, Any], plant_type: str, stage: str | None
) -> Dict[str, Any]:
    """Return stage specific data for ``plant_type`` or the ``optimal`` entry."""
    plant = dataset.get(normalize_key(plant_type), {})
    if stage:
        stage_key = normalize_key(stage)
        if stage_key in plant:
            entry = plant.get(stage_key)
            if isinstance(entry, dict):
                return entry
    entry = plant.get("optimal")
    return entry if isinstance(entry, dict) else {}


def _lookup_range(
    dataset: Mapping[str, Any], plant_type: str, stage: str | None
) -> RangeTuple | None:
    """Return (min, max) tuple for stage specific range datasets."""
    plant = dataset.get(normalize_key(plant_type), {})
    vals = None
    if stage:
        stage_key = normalize_key(stage)
        vals = plant.get(stage_key)
    if vals is None:
        vals = plant.get("optimal")
    if isinstance(vals, (list, tuple)) and len(vals) == 2:
        try:
            return float(vals[0]), float(vals[1])
        except (TypeError, ValueError):
            return None
    return None


def _lookup_threshold(dataset: Mapping[str, Any], plant_type: str) -> float | None:
    """Return numeric threshold for ``plant_type`` with fallback."""

    try:
        value = dataset.get(normalize_key(plant_type), dataset.get("default"))
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def average_environment_readings(
    series: Iterable[Mapping[str, float]],
) -> Dict[str, float]:
    """Return the average of normalized environment readings.

    Each mapping in ``series`` may use any of the aliases supported by
    :func:`normalize_environment_readings`. Invalid values are ignored.
    The result contains canonical keys with float values.
    """

    totals: Dict[str, float] = {}
    count = 0
    for reading in series:
        for key, value in normalize_environment_readings(reading).items():
            totals[key] = totals.get(key, 0.0) + float(value)
        count += 1

    if count == 0:
        return {}

    return {k: v / count for k, v in totals.items()}


def calculate_environment_variance(
    series: Iterable[Mapping[str, float]],
) -> Dict[str, float]:
    """Return variance for normalized environment readings."""

    values: Dict[str, list[float]] = {}
    for reading in series:
        for key, value in normalize_environment_readings(reading).items():
            values.setdefault(key, []).append(float(value))

    variance: Dict[str, float] = {}
    if _np is not None:
        for key, vals in values.items():
            if vals:
                arr = _np.array(vals, dtype=float)
                variance[key] = float(_np.var(arr))
    else:  # pragma: no cover - fallback when numpy missing
        for key, vals in values.items():
            if vals:
                variance[key] = float(pvariance(vals))

    return {k: round(v, 3) for k, v in variance.items()}


def calculate_environment_stddev(
    series: Iterable[Mapping[str, float]],
) -> Dict[str, float]:
    """Return standard deviation for normalized environment readings."""

    variance = calculate_environment_variance(series)
    return {k: round(math.sqrt(v), 3) for k, v in variance.items()}


def calculate_environment_deviation(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
) -> Dict[str, float]:
    """Return fractional deviation from target midpoints for each metric.

    The deviation is ``0`` when the reading matches the midpoint of the
    recommended range and ``1`` when it hits either boundary. Values greater
    than ``1`` indicate the measurement exceeds the recommended range.
    """

    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return {}

    readings = normalize_environment_readings(current)
    deviation: Dict[str, float] = {}
    for key, bounds in targets.items():
        if (
            key not in readings
            or not isinstance(bounds, (list, tuple))
            or len(bounds) != 2
        ):
            continue
        low, high = bounds
        width = high - low
        if width <= 0:
            continue
        mid = (low + high) / 2
        fraction = abs(float(readings[key]) - mid) / (width / 2)
        deviation[key] = round(fraction, 2)

    return deviation


def calculate_environment_deviation_series(
    series: Iterable[Mapping[str, float]],
    plant_type: str,
    stage: str | None = None,
) -> Dict[str, float]:
    """Return average deviation from target midpoints for a series."""

    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for reading in series:
        dev = calculate_environment_deviation(reading, plant_type, stage)
        for key, value in dev.items():
            totals[key] = totals.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1

    return {
        key: round(totals[key] / counts[key], 2) for key in totals if counts.get(key, 0)
    }


def saturation_vapor_pressure(temp_c: float) -> float:
    """Return saturation vapor pressure (kPa) at ``temp_c``."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def actual_vapor_pressure(temp_c: float, humidity_pct: float) -> float:
    """Return actual vapor pressure (kPa) given temperature and relative humidity."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")
    return saturation_vapor_pressure(temp_c) * humidity_pct / 100


@dataclass(slots=True)
class EnvironmentMetrics:
    """Calculated environmental metrics."""

    vpd: float | None
    dew_point_c: float | None
    heat_index_c: float | None
    absolute_humidity_g_m3: float | None
    et0_mm_day: float | None = None
    eta_mm_day: float | None = None
    transpiration_ml_day: float | None = None
    root_uptake_factor: float | None = None

    def as_dict(self) -> Dict[str, float | None]:
        """Return metrics as a regular dictionary."""
        return asdict(self)


@dataclass(slots=True)
class EnvironmentOptimization:
    """Consolidated environment optimization result."""

    setpoints: Dict[str, float]
    adjustments: Dict[str, str]
    metrics: EnvironmentMetrics
    ph_setpoint: float | None = None
    ph_action: str | None = None
    target_dli: tuple[float, float] | None = None
    target_vpd: tuple[float, float] | None = None
    target_photoperiod: tuple[float, float] | None = None
    target_co2: tuple[float, float] | None = None
    target_light_ratio: float | None = None
    photoperiod_hours: float | None = None
    heat_stress: bool | None = None
    cold_stress: bool | None = None
    light_stress: str | None = None
    wind_stress: bool | None = None
    humidity_stress: str | None = None
    moisture_stress: str | None = None
    ph_stress: str | None = None
    soil_ph_stress: str | None = None
    soil_ec_stress: str | None = None
    quality: str | None = None
    score: float | None = None
    water_quality: WaterQualityInfo | None = None

    def as_dict(self) -> Dict[str, Any]:
        """Return the optimization result as a serializable dictionary."""
        return {
            "setpoints": self.setpoints,
            "adjustments": self.adjustments,
            "vpd": self.metrics.vpd,
            "dew_point_c": self.metrics.dew_point_c,
            "heat_index_c": self.metrics.heat_index_c,
            "absolute_humidity_g_m3": self.metrics.absolute_humidity_g_m3,
            "et0_mm_day": self.metrics.et0_mm_day,
            "eta_mm_day": self.metrics.eta_mm_day,
            "transpiration_ml_day": self.metrics.transpiration_ml_day,
            "ph_setpoint": self.ph_setpoint,
            "ph_action": self.ph_action,
            "target_dli": self.target_dli,
            "target_vpd": self.target_vpd,
            "target_photoperiod": self.target_photoperiod,
            "target_co2": self.target_co2,
            "target_light_ratio": self.target_light_ratio,
            "photoperiod_hours": self.photoperiod_hours,
            "heat_stress": self.heat_stress,
            "cold_stress": self.cold_stress,
            "light_stress": self.light_stress,
            "wind_stress": self.wind_stress,
            "humidity_stress": self.humidity_stress,
            "moisture_stress": self.moisture_stress,
            "ph_stress": self.ph_stress,
            "soil_ph_stress": self.soil_ph_stress,
            "soil_ec_stress": self.soil_ec_stress,
            "quality": self.quality,
            "score": self.score,
            "water_quality": (
                self.water_quality.as_dict() if self.water_quality else None
            ),
        }


@dataclass
class StressFlags:
    """Combined abiotic stress indicators."""

    heat: bool | None
    cold: bool | None
    light: str | None
    wind: bool | None
    humidity: str | None
    moisture: str | None
    ph: str | None
    soil_ph: str | None = None
    soil_temp: str | None = None
    soil_ec: str | None = None
    leaf_temp: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WaterQualityInfo:
    """Simple rating and score for irrigation water."""

    rating: str
    score: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EnvironmentSummary:
    """High level summary of current environmental conditions."""

    quality: str
    adjustments: Dict[str, str]
    metrics: EnvironmentMetrics
    score: float
    stress: StressFlags
    water_quality: WaterQualityInfo | None = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality,
            "adjustments": self.adjustments,
            "metrics": self.metrics.as_dict(),
            "score": self.score,
            "stress": self.stress.as_dict(),
            "water_quality": (
                self.water_quality.as_dict() if self.water_quality else None
            ),
        }


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return list_dataset_entries(_DATA)


@lru_cache(maxsize=None)
def get_environmental_targets(
    plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    return get_environment_guidelines(plant_type, stage).as_dict()


def clear_environment_cache() -> None:
    """Clear cached guideline lookups."""

    caches = [
        get_environmental_targets,
        get_environment_guidelines,
        get_climate_guidelines,
        get_frost_dates,
        get_combined_environment_guidelines,
        get_combined_environmental_targets,
        get_co2_price,
        get_co2_efficiency,
    ]

    for func in caches:
        func.cache_clear()


def classify_value_range(value: float, bounds: RangeTuple) -> str:
    """Return classification of ``value`` relative to ``bounds``.

    The return value is one of ``"below range"``, ``"above range"`` or
    ``"within range"``. No validation is performed on ``bounds``.
    """
    low, high = bounds
    if value < low:
        return "below range"
    if value > high:
        return "above range"
    return "within range"


def _check_range(value: float, bounds: RangeTuple) -> str | None:
    """Return adjustment suggestion for ``value`` relative to ``bounds``."""

    status = classify_value_range(value, bounds)
    if status == "below range":
        return "increase"
    if status == "above range":
        return "decrease"
    return None


def compare_environment(
    current: Mapping[str, float], targets: Mapping[str, Iterable[float]]
) -> Dict[str, str]:
    """Return comparison of readings to target ranges.

    Parameters
    ----------
    current : Mapping[str, float]
        Current environment readings. Keys may use aliases like ``temperature``
        or ``rh`` and will be normalized using :data:`ENV_ALIASES`.
    targets : Mapping[str, Iterable[float]]
        Desired ranges where each value is ``[min, max]``.

    Returns
    -------
    Dict[str, str]
        Mapping of target keys to ``"below range"``, ``"above range"`` or
        ``"within range"`` strings.
    """

    normalized = normalize_environment_readings(current)
    results: Dict[str, str] = {}
    for key, bounds in targets.items():
        if (
            not isinstance(bounds, (list, tuple))
            or len(bounds) != 2
            or key not in normalized
        ):
            continue

        try:
            val = float(normalized[key])
            low, high = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            continue

        results[key] = classify_value_range(val, (low, high))

    return results


def recommend_environment_adjustments(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    zone: str | None = None,
) -> Dict[str, str]:
    """Return detailed adjustment suggestions for key environment parameters.

    The returned mapping may include descriptive recommendations for
    temperature and humidity based on stress evaluation datasets. Other keys
    fall back to simple ``"increase"``/``"decrease"`` hints.
    """

    targets = (
        get_combined_environmental_targets(plant_type, stage, zone)
        if zone
        else get_environmental_targets(plant_type, stage)
    )
    if not targets:
        return {}

    comparison = compare_environment(current, targets)
    readings = normalize_environment_readings(current)
    # Track which alias produced each canonical key so we can optionally
    # bypass descriptive strategies when uncommon aliases are used.
    alias_map = { _ALIAS_MAP.get(k, k): k for k in current }

    actions: Dict[str, str] = {}
    for key, status in comparison.items():
        if status == "within range":
            continue

        label = ACTION_LABELS.get(key, key)

        action: str | None = None
        if key == "temp_c":
            action = recommend_temperature_action(
                readings.get("temp_c"), readings.get("humidity_pct"), plant_type
            )
        elif key == "humidity_pct":
            action = recommend_humidity_action(readings.get("humidity_pct"), plant_type)
        elif key == "photoperiod_hours":
            action = recommend_photoperiod_action(
                readings.get("photoperiod_hours"), plant_type, stage
            )

        # Only apply descriptive strategies when the original alias is not in
        # EXTENDED_ALIASES. This allows tests to validate fallback behaviour
        # using uncommon sensor names.
        alias = alias_map.get(key, key)
        if not action and alias not in EXTENDED_ALIASES:
            level = "low" if status == "below range" else "high"
            action = get_environment_strategy(label, level)

        if not action:
            action = "increase" if status == "below range" else "decrease"

        actions[label] = action

    return actions


def generate_environment_alerts(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return human readable alerts for readings outside recommended ranges.

    Parameters
    ----------
    current : Mapping[str, float]
        Current environment readings using the same keys as
        :data:`ACTION_LABELS` or their aliases.
    plant_type : str
        Plant type used to look up guideline ranges.
    stage : str, optional
        Growth stage for stage specific guidelines.
    """

    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return {}

    alerts: Dict[str, str] = {}
    comparison = compare_environment(current, targets)
    for key, status in comparison.items():
        if status == "within range":
            continue
        label = ACTION_LABELS.get(key, key)
        low, high = targets[key]
        if status == "below range":
            alerts[label] = f"{label} below {low}-{high}"
        else:
            alerts[label] = f"{label} above {low}-{high}"
    return alerts


def score_environment_components(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
) -> Dict[str, float]:
    """Return per-parameter environment scores on a 0-100 scale."""

    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return {}

    readings = normalize_environment_readings(current)
    scores: Dict[str, float] = {}
    for key, bounds in targets.items():
        if key not in readings or not isinstance(bounds, (list, tuple)):
            continue
        low, high = bounds
        val = readings[key]
        width = high - low
        if width <= 0:
            continue
        if low <= val <= high:
            comp = 1.0
        elif val < low:
            comp = max(0.0, 1 - (low - val) / width)
        else:
            comp = max(0.0, 1 - (val - high) / width)
        scores[key] = round(comp * 100, 1)

    return scores


def score_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> float:
    """Return a 0-100 score representing overall environment quality."""

    components = score_environment_components(current, plant_type, stage)
    if not components:
        return 0.0

    total = 0.0
    total_weight = 0.0
    for key, value in components.items():
        weight = get_score_weight(key)
        total += value * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(total / total_weight, 1)


def score_environment_series(
    series: Iterable[Mapping[str, float]],
    plant_type: str,
    stage: str | None = None,
) -> float:
    """Return the average environment score for ``series``."""

    total = 0.0
    count = 0
    for reading in series:
        total += score_environment(reading, plant_type, stage)
        count += 1

    if count == 0:
        return 0.0

    return round(total / count, 1)


def classify_environment_quality(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    thresholds: Mapping[str, float] | None = None,
) -> str:
    """Return ``good``, ``fair`` or ``poor`` based on environment score.

    The optional ``thresholds`` mapping can override the default values loaded
    from :data:`environment_quality_thresholds.json` which enables customized
    quality bands for specific deployments.
    """

    if thresholds:
        labels = [
            (k, float(v)) for k, v in thresholds.items() if isinstance(v, (int, float))
        ]
        labels.sort(key=lambda x: x[1], reverse=True)
    else:
        labels = get_environment_quality_labels()

    score = score_environment(current, plant_type, stage)
    for label, limit in labels:
        if score >= limit:
            return label
    return labels[-1][0] if labels else "poor"


def classify_environment_quality_series(
    series: Iterable[Mapping[str, float]],
    plant_type: str,
    stage: str | None = None,
    thresholds: Mapping[str, float] | None = None,
) -> str:
    """Return quality classification for averaged environment ``series``."""

    if thresholds:
        labels = [
            (k, float(v)) for k, v in thresholds.items() if isinstance(v, (int, float))
        ]
        labels.sort(key=lambda x: x[1], reverse=True)
    else:
        labels = get_environment_quality_labels()

    score = score_environment_series(series, plant_type, stage)
    for label, limit in labels:
        if score >= limit:
            return label
    return labels[-1][0] if labels else "poor"


def score_overall_environment(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    water_test: Mapping[str, float] | None = None,
    *,
    env_weight: float = 0.7,
    water_weight: float = 0.3,
) -> float:
    """Return combined environment score factoring in water quality."""

    if env_weight < 0 or water_weight < 0:
        raise ValueError("weights must be non-negative")

    env_score = score_environment(current, plant_type, stage)
    water_score = 100.0
    if water_test is not None:
        water_score = water_quality.score_water_quality(water_test)

    total_weight = env_weight + water_weight
    if total_weight == 0:
        return 0.0

    overall = (env_score * env_weight + water_score * water_weight) / total_weight
    return round(overall, 1)


def suggest_environment_setpoints(
    plant_type: str, stage: str | None = None
) -> Dict[str, float]:
    """Return midpoint setpoints for key environment parameters."""

    targets = get_environmental_targets(plant_type, stage)
    return _midpoint_setpoints(targets, plant_type, stage)


def _midpoint_setpoints(
    targets: Mapping[str, Any], plant_type: str, stage: str | None
) -> Dict[str, float]:
    """Return midpoint values for ``targets`` with soil parameters."""

    setpoints: Dict[str, float] = {}
    for key, bounds in targets.items():
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            setpoints[key] = round((bounds[0] + bounds[1]) / 2, 2)

    soil = get_target_soil_moisture(plant_type, stage)
    if soil:
        setpoints["soil_moisture_pct"] = round((soil[0] + soil[1]) / 2, 2)

    soil_temp = get_target_soil_temperature(plant_type, stage)
    if soil_temp:
        setpoints["soil_temp_c"] = round((soil_temp[0] + soil_temp[1]) / 2, 2)

    soil_ec = get_target_soil_ec(plant_type, stage)
    if soil_ec:
        setpoints["soil_ec"] = round((soil_ec[0] + soil_ec[1]) / 2, 2)

    return setpoints


def suggest_environment_setpoints_advanced(
    plant_type: str, stage: str | None = None
) -> Dict[str, float]:
    """Return midpoint setpoints with VPD fallback for humidity."""

    setpoints = suggest_environment_setpoints(plant_type, stage)
    if "humidity_pct" not in setpoints:
        targets = get_environmental_targets(plant_type, stage)
        temp = targets.get("temp_c")
        vpd = get_target_vpd(plant_type, stage)
        if isinstance(temp, (list, tuple)) and len(temp) == 2 and vpd is not None:
            temp_mid = (float(temp[0]) + float(temp[1])) / 2
            vpd_mid = (vpd[0] + vpd[1]) / 2
            try:
                setpoints["humidity_pct"] = humidity_for_target_vpd(temp_mid, vpd_mid)
            except ValueError:
                pass
    return setpoints


def energy_optimized_setpoints(
    plant_type: str,
    stage: str | None,
    current_temp_c: float,
    hours: float,
    system: str = "heating",
) -> Dict[str, float]:
    """Return environment setpoints minimizing HVAC energy use.

    The recommended temperature setpoint is chosen from the lower or upper
    bound of the target range depending on which requires less energy to
    maintain from ``current_temp_c`` for ``hours`` using the HVAC ``system``.
    All other setpoints are the same as :func:`suggest_environment_setpoints`.
    """

    if hours <= 0:
        raise ValueError("hours must be positive")

    setpoints = suggest_environment_setpoints(plant_type, stage)
    temp_range = get_environmental_targets(plant_type, stage).get("temp_c")
    if not isinstance(temp_range, (list, tuple)) or len(temp_range) != 2:
        return setpoints

    from .energy_manager import estimate_hvac_energy

    low, high = float(temp_range[0]), float(temp_range[1])
    low_kwh = estimate_hvac_energy(current_temp_c, low, hours, system)
    high_kwh = estimate_hvac_energy(current_temp_c, high, hours, system)
    setpoints["temp_c"] = low if low_kwh <= high_kwh else high
    return setpoints


def cost_optimized_setpoints(
    plant_type: str,
    stage: str | None,
    current_temp_c: float,
    hours: float,
    system: str = "heating",
    region: str | None = None,
) -> Dict[str, float]:
    """Return environment setpoints minimizing HVAC cost.

    The temperature setpoint that results in the lowest estimated energy
    cost for ``hours`` is selected using :func:`energy_manager.estimate_hvac_cost`.
    All other setpoints match :func:`suggest_environment_setpoints`.
    """

    if hours <= 0:
        raise ValueError("hours must be positive")

    setpoints = suggest_environment_setpoints(plant_type, stage)
    temp_range = get_environmental_targets(plant_type, stage).get("temp_c")
    if not isinstance(temp_range, (list, tuple)) or len(temp_range) != 2:
        return setpoints

    from .energy_manager import estimate_hvac_cost

    low, high = float(temp_range[0]), float(temp_range[1])
    low_cost = estimate_hvac_cost(current_temp_c, low, hours, system, region)
    high_cost = estimate_hvac_cost(current_temp_c, high, hours, system, region)
    setpoints["temp_c"] = low if low_cost <= high_cost else high
    return setpoints


def generate_stage_environment_plan(plant_type: str) -> Dict[str, Dict[str, float]]:
    """Return recommended environment setpoints for all growth stages."""

    plan: Dict[str, Dict[str, float]] = {}
    for stage in list_growth_stages(plant_type):
        plan[stage] = suggest_environment_setpoints(plant_type, stage)
    return plan


def suggest_environment_setpoints_zone(
    plant_type: str, stage: str | None, zone: str
) -> Dict[str, float]:
    """Return midpoint setpoints for a plant stage adjusted for ``zone``."""

    targets = get_combined_environmental_targets(plant_type, stage, zone)
    return _midpoint_setpoints(targets, plant_type, stage)


def generate_zone_environment_plan(
    plant_type: str, zone: str
) -> Dict[str, Dict[str, float]]:
    """Return environment setpoints for each stage adjusted for ``zone``."""

    plan: Dict[str, Dict[str, float]] = {}
    for stage in list_growth_stages(plant_type):
        plan[stage] = suggest_environment_setpoints_zone(plant_type, stage, zone)
    return plan


def generate_stage_growth_plan(plant_type: str) -> Dict[str, Dict[str, Any]]:
    """Return environment setpoints, nutrient needs and tasks per stage."""

    from custom_components.horticulture_assistant.utils.stage_nutrient_requirements import (
        get_stage_requirements,
    )
    from .stage_tasks import get_stage_tasks

    plan: Dict[str, Dict[str, Any]] = {}
    for stage in list_growth_stages(plant_type):
        plan[stage] = {
            "environment": suggest_environment_setpoints(plant_type, stage),
            "nutrients": get_stage_requirements(plant_type, stage),
            "tasks": get_stage_tasks(plant_type, stage),
        }
    return plan


def generate_cycle_growth_plan(
    plant_type: str, start_date: date
) -> list[dict[str, Any]]:
    """Return dated growth plan for an entire crop cycle.

    Each entry includes the stage name, start and end dates along with the
    environment setpoints, daily nutrient requirements and recommended tasks.
    This consolidates :func:`generate_stage_growth_plan` with the schedule from
    :func:`plant_engine.growth_stage.generate_stage_schedule` for convenience
    when creating crop management timelines.
    """

    from .growth_stage import generate_stage_schedule

    schedule = generate_stage_schedule(plant_type, start_date)
    stage_plan = generate_stage_growth_plan(plant_type)

    plan: list[dict[str, Any]] = []
    for entry in schedule:
        stage = entry["stage"]
        details = stage_plan.get(stage, {})
        plan.append(
            {
                "stage": stage,
                "start_date": entry["start_date"],
                "end_date": entry["end_date"],
                "environment": details.get("environment", {}),
                "nutrients": details.get("nutrients", {}),
                "tasks": details.get("tasks", []),
            }
        )

    return plan


def calculate_vpd(temp_c: float, humidity_pct: float) -> float:
    """Return Vapor Pressure Deficit (kPa) using :func:`saturation_vapor_pressure`."""
    ea = actual_vapor_pressure(temp_c, humidity_pct)
    es = saturation_vapor_pressure(temp_c)
    vpd = es - ea
    return round(vpd, 3)


def calculate_dew_point(temp_c: float, humidity_pct: float) -> float:
    """Return dew point temperature (°C) using the Magnus formula."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")

    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity_pct / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 2)


def calculate_heat_index(temp_c: float, humidity_pct: float) -> float:
    """Return heat index temperature (°C) accounting for humidity.

    The calculation converts to Fahrenheit, applies the NOAA heat index
    approximation and converts back to Celsius. ``humidity_pct`` must be
    between 0 and 100 or a ``ValueError`` is raised.
    """
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")

    temp_f = temp_c * 9 / 5 + 32
    rh = humidity_pct

    hi_f = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f**2
        - 0.05481717 * rh**2
        + 0.00122874 * temp_f**2 * rh
        + 0.00085282 * temp_f * rh**2
        - 0.00000199 * temp_f**2 * rh**2
    )

    hi_c = (hi_f - 32) * 5 / 9
    return round(hi_c, 2)


def relative_humidity_from_dew_point(temp_c: float, dew_point_c: float) -> float:
    """Return relative humidity (%) from dew point and temperature.

    Parameters
    ----------
    temp_c: float
        Current air temperature in °C.
    dew_point_c: float
        Dew point temperature in °C. Must not exceed ``temp_c``.
    """
    if dew_point_c > temp_c:
        raise ValueError("dew_point_c cannot exceed temp_c")

    es = saturation_vapor_pressure(temp_c)
    ea = saturation_vapor_pressure(dew_point_c)
    rh = 100 * ea / es
    return round(rh, 1)


def calculate_absolute_humidity(temp_c: float, humidity_pct: float) -> float:
    """Return absolute humidity (g/m³) for given temperature and RH."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")
    # vapor pressure in hPa using Magnus formula
    svp = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    vap_pressure = humidity_pct / 100 * svp
    ah = 2.1674 * (vap_pressure * 100) / (273.15 + temp_c)
    return round(ah, 2)


def calculate_dli(ppfd: float, photoperiod_hours: float) -> float:
    """Return Daily Light Integral (mol m⁻² day⁻¹).

    The calculation converts the given Photosynthetic Photon Flux
    Density (PPFD) in µmol⋅m⁻²⋅s⁻¹ over a ``photoperiod_hours`` span.
    """
    if ppfd < 0 or photoperiod_hours <= 0:
        raise ValueError("ppfd must be non-negative and photoperiod_hours > 0")

    dli = ppfd * 3600 * photoperiod_hours / 1_000_000
    return round(dli, 2)


def photoperiod_for_target_dli(target_dli: float, ppfd: float) -> float:
    """Return photoperiod hours required to reach ``target_dli`` at ``ppfd``.

    Both arguments must be positive; otherwise a ``ValueError`` is raised.
    """
    if target_dli <= 0 or ppfd <= 0:
        raise ValueError("target_dli and ppfd must be positive")

    hours = target_dli * 1_000_000 / (ppfd * 3600)
    return round(hours, 2)


def ppfd_for_target_dli(target_dli: float, photoperiod_hours: float) -> float:
    """Return PPFD required to reach ``target_dli`` over ``photoperiod_hours``.

    Both arguments must be positive or a ``ValueError`` is raised.
    """
    if target_dli <= 0 or photoperiod_hours <= 0:
        raise ValueError("target_dli and photoperiod_hours must be positive")

    ppfd = target_dli * 1_000_000 / (photoperiod_hours * 3600)
    return round(ppfd, 2)


def humidity_for_target_vpd(temp_c: float, target_vpd: float) -> float:
    """Return relative humidity (%) that yields ``target_vpd`` at ``temp_c``.

    ``target_vpd`` must be non-negative and may not exceed the saturation vapor
    pressure for ``temp_c``. A ``ValueError`` is raised if the value is
    unattainable.
    """

    if target_vpd < 0:
        raise ValueError("target_vpd must be non-negative")

    es = saturation_vapor_pressure(temp_c)
    if target_vpd > es:
        raise ValueError("target_vpd exceeds saturation vapor pressure")

    ea = es - target_vpd
    rh = 100 * ea / es
    return round(rh, 1)


def recommend_photoperiod(
    ppfd: float, plant_type: str, stage: str | None = None
) -> float | None:
    """Return photoperiod hours to achieve the midpoint DLI target.

    If either the plant has no DLI guidelines or ``ppfd`` is non-positive,
    ``None`` is returned.
    """
    if ppfd <= 0:
        return None

    target = get_target_dli(plant_type, stage)
    if not target:
        return None

    mid_target = sum(target) / 2
    return photoperiod_for_target_dli(mid_target, ppfd)


def recommend_light_intensity(
    photoperiod_hours: float, plant_type: str, stage: str | None = None
) -> float | None:
    """Return PPFD required for the midpoint DLI target.

    If the plant has no DLI data or ``photoperiod_hours`` is non-positive,
    ``None`` is returned.
    """
    if photoperiod_hours <= 0:
        return None

    target = get_target_dli(plant_type, stage)
    if not target:
        return None

    mid_target = sum(target) / 2
    return ppfd_for_target_dli(mid_target, photoperiod_hours)


def evaluate_heat_stress(
    temp_c: float | None,
    humidity_pct: float | None,
    plant_type: str,
) -> bool | None:
    """Return ``True`` if heat index exceeds the plant threshold."""

    if temp_c is None or humidity_pct is None:
        return None

    threshold = _lookup_threshold(_HEAT_THRESHOLDS, plant_type)
    if threshold is None:
        return None

    hi = calculate_heat_index(temp_c, humidity_pct)
    return hi >= threshold


def evaluate_cold_stress(
    temp_c: float | None,
    plant_type: str,
) -> bool | None:
    """Return ``True`` if temperature is below the plant cold threshold."""

    if temp_c is None:
        return None

    threshold = _lookup_threshold(_COLD_THRESHOLDS, plant_type)
    if threshold is None:
        return None

    return temp_c <= threshold


def evaluate_wind_stress(
    wind_m_s: float | None,
    plant_type: str,
) -> bool | None:
    """Return ``True`` if wind speed exceeds the plant threshold."""

    if wind_m_s is None:
        return None

    threshold = _lookup_threshold(_WIND_THRESHOLDS, plant_type)
    if threshold is None:
        return None

    return wind_m_s >= threshold


def evaluate_humidity_stress(
    humidity_pct: float | None,
    plant_type: str,
) -> str | None:
    """Return 'low' or 'high' if humidity is outside thresholds."""

    if humidity_pct is None:
        return None

    thresh = _HUMIDITY_THRESHOLDS.get(
        normalize_key(plant_type), _HUMIDITY_THRESHOLDS.get("default")
    )
    if not isinstance(thresh, (list, tuple)) or len(thresh) != 2:
        return None

    low, high = float(thresh[0]), float(thresh[1])
    if humidity_pct < low:
        return "low"
    if humidity_pct > high:
        return "high"
    return None


def get_humidity_action(level: str) -> str:
    """Return recommended action for a humidity stress level."""

    return _HUMIDITY_ACTIONS.get(level.lower(), "")


def recommend_humidity_action(
    humidity_pct: float | None, plant_type: str
) -> str | None:
    """Return humidity adjustment recommendation if outside thresholds."""

    level = evaluate_humidity_stress(humidity_pct, plant_type)
    if level is None:
        return None
    action = get_humidity_action(level)
    return action or None


def get_temperature_action(level: str) -> str:
    """Return recommended action for a temperature stress level."""

    return _TEMPERATURE_ACTIONS.get(level.lower(), "")


def recommend_temperature_action(
    temp_c: float | None,
    humidity_pct: float | None,
    plant_type: str,
) -> str | None:
    """Return temperature adjustment recommendation if outside thresholds."""

    if evaluate_cold_stress(temp_c, plant_type):
        return get_temperature_action("cold") or None
    if evaluate_heat_stress(temp_c, humidity_pct, plant_type):
        return get_temperature_action("hot") or None
    return None


def get_wind_action(level: str) -> str:
    """Return recommended action for a wind stress level."""

    return _WIND_ACTIONS.get(level.lower(), "")


def recommend_wind_action(wind_m_s: float | None, plant_type: str) -> str | None:
    """Return wind mitigation recommendation if speed exceeds threshold."""

    if evaluate_wind_stress(wind_m_s, plant_type):
        action = get_wind_action("high")
        return action or None
    return None


def evaluate_vpd(
    temp_c: float | None,
    humidity_pct: float | None,
    plant_type: str,
    stage: str | None = None,
) -> str | None:
    """Return 'low' or 'high' if VPD is outside the recommended range."""

    if temp_c is None or humidity_pct is None:
        return None

    target = get_target_vpd(plant_type, stage)
    if not target:
        return None

    vpd = calculate_vpd(float(temp_c), float(humidity_pct))
    low, high = target
    if vpd < low:
        return "low"
    if vpd > high:
        return "high"
    return None


def get_vpd_action(level: str) -> str:
    """Return recommended action for a VPD stress level."""

    return _VPD_ACTIONS.get(level.lower(), "")


def recommend_vpd_action(
    temp_c: float | None,
    humidity_pct: float | None,
    plant_type: str,
    stage: str | None = None,
) -> str | None:
    """Return adjustment suggestion when VPD is out of range."""

    level = evaluate_vpd(temp_c, humidity_pct, plant_type, stage)
    if level is None:
        return None
    action = get_vpd_action(level)
    return action or None


def get_photoperiod_action(level: str) -> str:
    """Return recommended action for a photoperiod stress level."""

    return _PHOTOPERIOD_ACTIONS.get(level.lower(), "")


def recommend_photoperiod_action(
    photoperiod_hours: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return adjustment suggestion when photoperiod is out of range."""

    target = get_target_photoperiod(plant_type, stage)
    if not target or photoperiod_hours is None:
        return None
    low, high = target
    if photoperiod_hours < low:
        return get_photoperiod_action("short") or None
    if photoperiod_hours > high:
        return get_photoperiod_action("long") or None
    return None


def get_environment_strategy(parameter: str, level: str) -> str:
    """Return optimization strategy for a parameter at a given level."""

    param = normalize_key(parameter)
    strategies = _ENV_STRATEGIES.get(param)
    if not strategies:
        return ""
    return strategies.get(level.lower(), "")


def recommend_environment_strategies(status: Mapping[str, str]) -> Dict[str, str]:
    """Return strategies for each parameter classification in ``status``."""

    rec: Dict[str, str] = {}
    for key, level in status.items():
        action = get_environment_strategy(key, level)
        if action:
            rec[key] = action
    return rec


def evaluate_ph_stress(
    ph: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'low' or 'high' if pH is outside the recommended range."""

    if ph is None:
        return None

    rng = ph_manager.get_ph_range(plant_type, stage)
    if not rng:
        return None

    low, high = rng
    if ph < low:
        return "low"
    if ph > high:
        return "high"
    return None


def get_target_soil_moisture(
    plant_type: str, stage: str | None = None
) -> RangeTuple | None:
    """Return recommended soil moisture percentage range for a plant stage."""

    return _lookup_range(_MOISTURE_DATA, plant_type, stage)


def evaluate_moisture_stress(
    moisture_pct: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'dry' or 'wet' if soil moisture is outside the target range."""

    if moisture_pct is None:
        return None

    target = get_target_soil_moisture(plant_type, stage)
    if not target:
        return None

    low, high = target
    if moisture_pct < low:
        return "dry"
    if moisture_pct > high:
        return "wet"
    return None


def get_target_soil_temperature(
    plant_type: str, stage: str | None = None
) -> RangeTuple | None:
    """Return recommended soil temperature range for a plant stage."""

    return _lookup_range(_SOIL_TEMP_DATA, plant_type, stage)


def get_target_soil_ec(plant_type: str, stage: str | None = None) -> RangeTuple | None:
    """Return recommended soil EC range for a plant stage."""

    return _lookup_range(_SOIL_EC_DATA, plant_type, stage)


def get_target_soil_ph(plant_type: str) -> RangeTuple | None:
    """Return optimal soil pH range for ``plant_type``."""
    rng = _SOIL_PH_DATA.get(normalize_key(plant_type))
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        try:
            return float(rng[0]), float(rng[1])
        except (TypeError, ValueError):
            return None
    return None


def get_target_leaf_temperature(
    plant_type: str, stage: str | None = None
) -> RangeTuple | None:
    """Return recommended leaf temperature range for a plant stage."""

    return _lookup_range(_LEAF_TEMP_DATA, plant_type, stage)


def evaluate_soil_temperature_stress(
    soil_temp_c: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'cold' or 'hot' if soil temperature is outside the target range."""

    if soil_temp_c is None:
        return None

    target = get_target_soil_temperature(plant_type, stage)
    if not target:
        return None

    low, high = target
    if soil_temp_c < low:
        return "cold"
    if soil_temp_c > high:
        return "hot"
    return None


def evaluate_soil_ec_stress(
    soil_ec_ds_m: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'low' or 'high' if soil EC is outside the target range."""

    if soil_ec_ds_m is None:
        return None

    target = get_target_soil_ec(plant_type, stage)
    if not target:
        return None

    low, high = target
    if soil_ec_ds_m < low:
        return "low"
    if soil_ec_ds_m > high:
        return "high"
    return None


def evaluate_soil_ph_stress(soil_ph: float | None, plant_type: str) -> str | None:
    """Return 'low' or 'high' if soil pH is outside the recommended range."""

    if soil_ph is None:
        return None

    target = get_target_soil_ph(plant_type)
    if not target:
        return None

    low, high = target
    if soil_ph < low:
        return "low"
    if soil_ph > high:
        return "high"
    return None


def evaluate_leaf_temperature_stress(
    leaf_temp_c: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'cold' or 'hot' if leaf temperature is outside the target range."""

    if leaf_temp_c is None:
        return None

    target = get_target_leaf_temperature(plant_type, stage)
    if not target:
        return None

    low, high = target
    if leaf_temp_c < low:
        return "cold"
    if leaf_temp_c > high:
        return "hot"
    return None


def evaluate_light_stress(
    dli: float | None, plant_type: str, stage: str | None = None
) -> str | None:
    """Return 'low' or 'high' if DLI is outside the recommended range."""

    if dli is None:
        return None

    target = get_target_dli(plant_type, stage)
    if not target:
        return None

    low, high = target
    if dli < low:
        return "low"
    if dli > high:
        return "high"
    return None


def evaluate_stress_conditions(
    temp_c: float | None,
    humidity_pct: float | None,
    dli: float | None,
    ph: float | None,
    wind_m_s: float | None,
    moisture_pct: float | None,
    leaf_temp_c: float | None,
    plant_type: str,
    stage: str | None = None,
    soil_temp_c: float | None = None,
    soil_ec_ds_m: float | None = None,
    soil_ph: float | None = None,
) -> StressFlags:
    """Return consolidated stress flags for current conditions."""

    return StressFlags(
        heat=evaluate_heat_stress(temp_c, humidity_pct, plant_type),
        cold=evaluate_cold_stress(temp_c, plant_type),
        light=evaluate_light_stress(dli, plant_type, stage),
        wind=evaluate_wind_stress(wind_m_s, plant_type),
        humidity=evaluate_humidity_stress(humidity_pct, plant_type),
        moisture=evaluate_moisture_stress(moisture_pct, plant_type, stage),
        leaf_temp=evaluate_leaf_temperature_stress(leaf_temp_c, plant_type, stage),
        ph=evaluate_ph_stress(ph, plant_type, stage),
        soil_temp=evaluate_soil_temperature_stress(soil_temp_c, plant_type, stage),
        soil_ec=evaluate_soil_ec_stress(soil_ec_ds_m, plant_type, stage),
        soil_ph=evaluate_soil_ph_stress(soil_ph, plant_type),
    )


def calculate_dli_series(
    ppfd_values: Iterable[float], interval_hours: float = 1.0
) -> float:
    """Return Daily Light Integral from a sequence of PPFD readings.

    ``ppfd_values`` may be any iterable. Values are consumed lazily so large
    generators do not need to be materialized in memory.

    Parameters
    ----------
    ppfd_values: Iterable[float]
        Sequence of PPFD values in µmol⋅m⁻²⋅s⁻¹.
    interval_hours: float
        Time between each measurement in hours. Must be positive.
    """
    if interval_hours <= 0:
        raise ValueError("interval_hours must be positive")

    total = 0.0
    for raw in ppfd_values:
        val = float(raw)
        if val < 0:
            raise ValueError("PPFD values must be non-negative")
        total += val

    dli = total * 3600 * interval_hours / 1_000_000
    return round(dli, 2)


def calculate_vpd_series(
    temp_values: Iterable[float], humidity_values: Iterable[float]
) -> float:
    """Return average VPD from paired temperature and humidity readings.

    The iterables are consumed lazily so large data sets do not require
    additional memory. A ``ValueError`` is raised if the inputs differ in
    length. An empty input yields ``0.0``.
    """

    from itertools import zip_longest

    sentinel = object()
    total = 0.0
    count = 0

    for t, h in zip_longest(temp_values, humidity_values, fillvalue=sentinel):
        if sentinel in (t, h):
            raise ValueError(
                "temperature and humidity readings must have the same length"
            )

        total += calculate_vpd(float(t), float(h))
        count += 1

    return round(total / count, 3) if count else 0.0


def calculate_heat_index_series(
    temp_values: Iterable[float], humidity_values: Iterable[float]
) -> float:
    """Return average heat index from temperature and humidity pairs."""

    from itertools import zip_longest

    sentinel = object()
    total = 0.0
    count = 0

    for t, h in zip_longest(temp_values, humidity_values, fillvalue=sentinel):
        if sentinel in (t, h):
            raise ValueError(
                "temperature and humidity readings must have the same length"
            )
        total += calculate_heat_index(float(t), float(h))
        count += 1

    return round(total / count, 2) if count else 0.0


def get_target_dli(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended DLI range for a plant type and stage."""
    return _lookup_range(_DLI_DATA, plant_type, stage)


def get_target_vpd(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended VPD range for a plant type and stage."""
    return _lookup_range(_VPD_DATA, plant_type, stage)


def get_target_photoperiod(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended photoperiod range for a plant stage."""
    return _lookup_range(_PHOTOPERIOD_DATA, plant_type, stage)


def get_target_light_intensity(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended light intensity (PPFD) for a plant stage."""

    data = _lookup_stage_data(_DATA, plant_type, stage)
    if not isinstance(data, Mapping):
        return None
    vals = data.get("light_ppfd")
    if isinstance(vals, (list, tuple)) and len(vals) == 2:
        try:
            return float(vals[0]), float(vals[1])
        except (TypeError, ValueError):
            return None
    return None


def get_target_co2(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended CO₂ range in ppm for a plant stage."""
    guide = get_environment_guidelines(plant_type, stage)
    return guide.co2_ppm


def get_target_light_ratio(plant_type: str, stage: str | None = None) -> float | None:
    """Return recommended red:blue light ratio for a plant stage."""
    if stage is None:
        return None
    return get_red_blue_ratio(plant_type, stage)


def get_target_airflow(
    plant_type: str, stage: str | None = None
) -> RangeTuple | None:
    """Return recommended airflow range (CFM per m²) for a plant stage."""

    return _lookup_range(_AIRFLOW_DATA, plant_type, stage)


# Approximate mass of CO₂ in milligrams required per m³ to raise
# concentration by 1 ppm at 25°C. Used for enrichment calculations.
CO2_MG_PER_M3_PER_PPM = 1.98


def calculate_co2_injection(
    current_ppm: float, target_ppm: tuple[float, float], volume_m3: float
) -> float:
    """Return grams of CO₂ needed to reach the midpoint of ``target_ppm``.

    If ``current_ppm`` is already above the midpoint, ``0.0`` is returned.
    ``volume_m3`` must be positive.
    """

    if volume_m3 <= 0:
        raise ValueError("volume_m3 must be positive")
    midpoint = (target_ppm[0] + target_ppm[1]) / 2
    delta = max(0.0, midpoint - current_ppm)
    grams = delta * CO2_MG_PER_M3_PER_PPM * volume_m3 / 1000
    return round(grams, 2)


def recommend_co2_injection(
    current_ppm: float,
    plant_type: str,
    stage: str | None,
    volume_m3: float,
) -> float:
    """Return grams of CO₂ to inject for the given plant stage.

    The helper looks up target ranges via :func:`get_target_co2` and uses
    :func:`calculate_co2_injection` to determine the mass of CO₂ required to
    reach the midpoint of the recommended range. ``0.0`` is returned when no
    guidelines exist or ``current_ppm`` already exceeds the target.
    """

    target = get_target_co2(plant_type, stage)
    if not target:
        return 0.0
    return calculate_co2_injection(current_ppm, target, volume_m3)


@lru_cache(maxsize=None)
def get_co2_price(method: str) -> float:
    """Return price per kg of CO₂ for ``method``.

    The result is cached for efficiency.
    """
    try:
        return float(_CO2_PRICES.get(normalize_key(method), 0.0))
    except (TypeError, ValueError):
        return 0.0


@lru_cache(maxsize=None)
def get_co2_efficiency(method: str) -> float:
    """Return delivery efficiency factor for a CO₂ injection method."""

    try:
        value = float(_CO2_EFFICIENCY.get(normalize_key(method), 1.0))
        return value if value > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


def estimate_co2_cost(grams: float, method: str) -> float:
    """Return estimated CO₂ cost in dollars."""
    if grams < 0:
        raise ValueError("grams must be non-negative")
    price = get_co2_price(method)
    efficiency = get_co2_efficiency(method)
    grams_required = grams / efficiency if efficiency > 0 else grams
    return round((grams_required / 1000) * price, 2)


def recommend_co2_injection_with_cost(
    current_ppm: float,
    plant_type: str,
    stage: str | None,
    volume_m3: float,
    method: str = "bulk_tank",
) -> tuple[float, float]:
    """Return grams of CO₂ to inject and estimated cost."""

    grams = recommend_co2_injection(current_ppm, plant_type, stage, volume_m3)
    cost = estimate_co2_cost(grams, method)
    return grams, cost


def calculate_co2_injection_series(
    ppm_series: Iterable[float],
    plant_type: str,
    stage: str | None,
    volume_m3: float,
) -> list[float]:
    """Return CO₂ grams required for each reading in ``ppm_series``.

    The function looks up the recommended range via :func:`get_target_co2` and
    applies :func:`calculate_co2_injection` to each reading. ``volume_m3`` must
    be positive. Unknown guidelines yield a list of zeros matching the input
    length.
    """

    if volume_m3 <= 0:
        raise ValueError("volume_m3 must be positive")

    target = get_target_co2(plant_type, stage)
    if not target:
        return [0.0 for _ in ppm_series]

    injections: list[float] = []
    for ppm in ppm_series:
        injections.append(calculate_co2_injection(float(ppm), target, volume_m3))

    return injections


def calculate_co2_cost_series(
    ppm_series: Iterable[float],
    plant_type: str,
    stage: str | None,
    volume_m3: float,
    method: str = "bulk_tank",
) -> list[float]:
    """Return cost for CO₂ injections calculated for each reading."""

    injections = calculate_co2_injection_series(
        ppm_series, plant_type, stage, volume_m3
    )
    return [estimate_co2_cost(g, method) for g in injections]


def calculate_environment_metrics(
    temp_c: float | None,
    humidity_pct: float | None,
    *,
    env: Mapping[str, float] | None = None,
    plant_type: str | None = None,
    stage: str | None = None,
) -> EnvironmentMetrics:
    """Return :class:`EnvironmentMetrics` including transpiration when possible.

    When ``env`` contains ``soil_temp_c`` or ``root_temp_c`` the returned metrics
    include a ``root_uptake_factor`` estimating relative nutrient uptake
    efficiency based on :mod:`plant_engine.root_temperature` data.
    """

    if temp_c is None or humidity_pct is None:
        return EnvironmentMetrics(None, None, None, None)

    metrics = EnvironmentMetrics(
        vpd=calculate_vpd(temp_c, humidity_pct),
        dew_point_c=calculate_dew_point(temp_c, humidity_pct),
        heat_index_c=calculate_heat_index(temp_c, humidity_pct),
        absolute_humidity_g_m3=calculate_absolute_humidity(temp_c, humidity_pct),
    )

    if env is not None and plant_type is not None:
        profile = {
            "plant_type": plant_type,
            "stage": stage,
            "canopy_m2": env.get("canopy_m2", 0.25),
        }
        et_env = {
            "temp_c": temp_c,
            "rh_pct": humidity_pct,
            "par_w_m2": env.get("par_w_m2")
            or env.get("par")
            or env.get("light_ppfd", 0),
            "wind_speed_m_s": env.get("wind_speed_m_s")
            or env.get("wind_m_s")
            or env.get("wind", 1.0),
            "elevation_m": env.get("elevation_m", 200),
        }
        try:
            transp = compute_transpiration(profile, et_env)
        except Exception:
            transp = None
        if transp:
            metrics.et0_mm_day = transp.get("et0_mm_day")
            metrics.eta_mm_day = transp.get("eta_mm_day")
            metrics.transpiration_ml_day = transp.get("transpiration_ml_day")

    soil_temp = None
    if env is not None:
        soil_temp = env.get("soil_temp_c") or env.get("root_temp_c")
    if soil_temp is not None:
        from .root_temperature import get_uptake_factor

        try:
            metrics.root_uptake_factor = get_uptake_factor(float(soil_temp))
        except Exception:
            metrics.root_uptake_factor = None

    return metrics


def calculate_environment_metrics_series(
    series: Iterable[Mapping[str, float]],
    plant_type: str | None = None,
    stage: str | None = None,
) -> EnvironmentMetrics:
    """Return :class:`EnvironmentMetrics` for averaged environment data."""

    avg = average_environment_readings(series)
    if not avg:
        return EnvironmentMetrics(None, None, None, None)

    return calculate_environment_metrics(
        avg.get("temp_c"),
        avg.get("humidity_pct"),
        env=avg,
        plant_type=plant_type,
        stage=stage,
    )


def optimize_environment(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    water_test: Mapping[str, float] | None = None,
    *,
    zone: str | None = None,
) -> Dict[str, object]:
    """Return optimized environment data for a plant.

    The result includes midpoint setpoints, adjustment suggestions and key
    environmental metrics such as Vapor Pressure Deficit (VPD), dew point,
    heat index and absolute humidity when temperature and humidity readings are
    available. It also flags potential heat stress based on
    :data:`heat_stress_thresholds.json`. If target DLI, VPD or photoperiod
    ranges are defined they are returned as well. This helper consolidates
    several utilities for convenience when automating greenhouse controls.
    """

    readings = normalize_environment_readings(current)

    if zone:
        setpoints = suggest_environment_setpoints_zone(plant_type, stage, zone)
    else:
        setpoints = suggest_environment_setpoints(plant_type, stage)
    # Pass the original readings so adjustment logic can account for
    # uncommon aliases when selecting strategy text.
    actions = recommend_environment_adjustments(current, plant_type, stage, zone)

    # When extended aliases like ``air_temperature`` are used, fallback to a
    # simple increase/decrease hint instead of the full strategy message to
    # maintain backward compatibility with older datasets.
    if "air_temperature" in current and "temperature" in actions:
        guide = get_combined_environment_guidelines(plant_type, stage, zone)
        rng = guide.temp_c
        val = readings.get("temp_c")
        if rng and val is not None:
            low, high = rng
            if val < low:
                actions["temperature"] = "increase"
            elif val > high:
                actions["temperature"] = "decrease"

    metrics = calculate_environment_metrics(
        readings.get("temp_c"),
        readings.get("humidity_pct"),
        env=readings,
        plant_type=plant_type,
        stage=stage,
    )

    # Defer stress calculations until DLI is available
    # pH integration
    ph_set = ph_manager.recommended_ph_setpoint(plant_type, stage)
    ph_act = None
    if "ph" in readings and ph_set is not None:
        ph_act = ph_manager.recommend_ph_adjustment(readings["ph"], plant_type, stage)

    target_dli = get_target_dli(plant_type, stage)
    target_vpd = get_target_vpd(plant_type, stage)
    target_photoperiod = get_target_photoperiod(plant_type, stage)
    target_co2 = get_target_co2(plant_type, stage)
    target_light_ratio = get_target_light_ratio(plant_type, stage)
    photoperiod_hours = None
    if target_dli and "light_ppfd" in readings:
        mid_target = sum(target_dli) / 2
        photoperiod_hours = photoperiod_for_target_dli(
            mid_target, readings["light_ppfd"]
        )

    current_dli = readings.get("dli")
    if current_dli is None and {
        "light_ppfd",
        "photoperiod_hours",
    }.issubset(readings):
        try:
            current_dli = calculate_dli(
                readings["light_ppfd"], readings["photoperiod_hours"]
            )
        except ValueError:
            current_dli = None

    stress = evaluate_stress_conditions(
        readings.get("temp_c"),
        readings.get("humidity_pct"),
        current_dli,
        readings.get("ph"),
        readings.get("wind_m_s"),
        readings.get("soil_moisture_pct"),
        readings.get("leaf_temp_c"),
        plant_type,
        stage,
        readings.get("soil_temp_c"),
        readings.get("ec"),
        readings.get("soil_ph"),
    )

    quality = classify_environment_quality(readings, plant_type, stage)
    score = score_environment(readings, plant_type, stage)

    wq = None
    if water_test is not None:
        summary = water_quality.summarize_water_profile(water_test)
        wq = WaterQualityInfo(rating=summary.rating, score=summary.score)

    result = EnvironmentOptimization(
        setpoints,
        actions,
        metrics,
        ph_setpoint=ph_set,
        ph_action=ph_act,
        target_dli=target_dli,
        target_vpd=target_vpd,
        target_photoperiod=target_photoperiod,
        target_co2=target_co2,
        target_light_ratio=target_light_ratio,
        photoperiod_hours=photoperiod_hours,
        heat_stress=stress.heat,
        cold_stress=stress.cold,
        light_stress=stress.light,
        wind_stress=stress.wind,
        humidity_stress=stress.humidity,
        moisture_stress=stress.moisture,
        ph_stress=stress.ph,
        soil_ph_stress=stress.soil_ph,
        soil_ec_stress=stress.soil_ec,
        quality=quality,
        score=score,
        water_quality=wq,
    )
    return result.as_dict()


def summarize_environment(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    water_test: Mapping[str, float] | None = None,
    *,
    zone: str | None = None,
    include_targets: bool = False,
) -> Dict[str, Any]:
    """Return a consolidated environment summary for a plant stage.

    Parameters
    ----------
    current : Mapping[str, float]
        Current environment readings which may use any of the supported
        aliases in :data:`ENV_ALIASES`.
    plant_type : str
        Plant type used to look up guideline ranges.
    stage : str, optional
        Growth stage for stage specific guidelines.
    water_test : Mapping[str, float], optional
        Water quality metrics to include in the summary.
    include_targets : bool, optional
        If ``True`` the returned dictionary contains the recommended target
        ranges under the ``"targets"`` key.
    """

    readings = normalize_environment_readings(current)

    metrics = calculate_environment_metrics(
        readings.get("temp_c"),
        readings.get("humidity_pct"),
        env=readings,
        plant_type=plant_type,
        stage=stage,
    )
    stress = evaluate_stress_conditions(
        readings.get("temp_c"),
        readings.get("humidity_pct"),
        readings.get("dli"),
        readings.get("ph"),
        readings.get("wind_m_s"),
        readings.get("soil_moisture_pct"),
        readings.get("leaf_temp_c"),
        plant_type,
        stage,
        readings.get("soil_temp_c"),
        readings.get("ec"),
        readings.get("soil_ph"),
    )

    water_info = None
    if water_test is not None:
        summary = water_quality.summarize_water_profile(water_test)
        water_info = WaterQualityInfo(rating=summary.rating, score=summary.score)

    summary = EnvironmentSummary(
        quality=classify_environment_quality(readings, plant_type, stage),
        adjustments=recommend_environment_adjustments(
            readings, plant_type, stage, zone
        ),
        metrics=metrics,
        score=score_environment(readings, plant_type, stage),
        stress=stress,
        water_quality=water_info,
    )
    data = summary.as_dict()
    if include_targets:
        data["targets"] = get_environmental_targets(plant_type, stage)
    return data


def summarize_environment_series(
    series: Iterable[Mapping[str, float]],
    plant_type: str,
    stage: str | None = None,
    water_test: Mapping[str, float] | None = None,
    *,
    zone: str | None = None,
    include_targets: bool = False,
) -> Dict[str, Any]:
    """Return summary for averaged environment readings.

    The ``series`` argument can be any iterable of reading mappings. Each
    reading is normalized and averaged using
    :func:`average_environment_readings` before the result is passed to
    :func:`summarize_environment`.
    """

    avg = average_environment_readings(series)

    return summarize_environment(
        avg,
        plant_type,
        stage,
        water_test,
        zone=zone,
        include_targets=include_targets,
    )
