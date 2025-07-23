"""Utilities for environment targets and optimization helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Any, Dict, Mapping, Tuple, Iterable

from .utils import load_dataset, normalize_key, list_dataset_entries
from . import ph_manager, water_quality
from .compute_transpiration import compute_transpiration

DATA_FILE = "environment_guidelines.json"
DLI_DATA_FILE = "light_dli_guidelines.json"
VPD_DATA_FILE = "vpd_guidelines.json"
PHOTOPERIOD_DATA_FILE = "photoperiod_guidelines.json"
HEAT_DATA_FILE = "heat_stress_thresholds.json"
COLD_DATA_FILE = "cold_stress_thresholds.json"
WIND_DATA_FILE = "wind_stress_thresholds.json"
HUMIDITY_DATA_FILE = "humidity_stress_thresholds.json"
HUMIDITY_ACTION_FILE = "humidity_actions.json"
SCORE_WEIGHT_FILE = "environment_score_weights.json"

# map of dataset keys to human readable labels used when recommending
# adjustments. defined here once to avoid recreating each call.
ACTION_LABELS = {
    "temp_c": "temperature",
    "humidity_pct": "humidity",
    "light_ppfd": "light",
    "co2_ppm": "co2",
}

# aliases for environment keys used when comparing readings. This allows
# ``compare_environment`` to match sensor names like ``temperature`` or
# ``rh`` against dataset keys such as ``temp_c`` or ``humidity_pct``.
ENV_ALIASES = {
    "temp_c": ["temp_c", "temperature", "temp", "temperature_c"],
    # Fahrenheit readings are converted to Celsius during normalization
    "temp_f": ["temp_f", "temperature_f", "temp_fahrenheit"],
    "humidity_pct": ["humidity_pct", "humidity", "rh", "rh_pct"],
    "light_ppfd": ["light_ppfd", "light", "par", "par_w_m2"],
    "co2_ppm": ["co2_ppm", "co2"],
    "ec": ["ec", "EC"],
    "wind_m_s": ["wind_m_s", "wind", "wind_speed"],
}

# reverse mapping for constant time alias lookups
_ALIAS_MAP: Dict[str, str] = {
    alias: canonical
    for canonical, aliases in ENV_ALIASES.items()
    for alias in aliases
}


def _parse_range(value: Iterable[float]) -> Tuple[float, float] | None:
    """Return a normalized (min, max) tuple or ``None`` if invalid."""
    try:
        low, high = value
        low = float(low)
        high = float(high)
    except (TypeError, ValueError, Exception):
        return None
    return (low, high)


@dataclass(frozen=True)
class EnvironmentGuidelines:
    """Environmental target ranges for a plant stage."""

    temp_c: Tuple[float, float] | None = None
    humidity_pct: Tuple[float, float] | None = None
    light_ppfd: Tuple[float, float] | None = None
    co2_ppm: Tuple[float, float] | None = None

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
        temp_c=_parse_range(data.get("temp_c")),
        humidity_pct=_parse_range(data.get("humidity_pct")),
        light_ppfd=_parse_range(data.get("light_ppfd")),
        co2_ppm=_parse_range(data.get("co2_ppm")),
    )


def normalize_environment_readings(readings: Mapping[str, float]) -> Dict[str, float]:
    """Return ``readings`` with keys mapped to canonical environment names."""

    normalized: Dict[str, float] = {}
    for key, value in readings.items():
        canonical = _ALIAS_MAP.get(key, key)
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if canonical == "temp_f":
            val = (val - 32) * 5 / 9
            canonical = "temp_c"
        normalized[canonical] = val
    return normalized


__all__ = [
    "list_supported_plants",
    "get_environment_guidelines",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "score_environment",
    "score_environment_series",
    "score_environment_components",
    "suggest_environment_setpoints",
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
    "get_target_dli",
    "get_target_vpd",
    "get_target_photoperiod",
    "get_target_co2",
    "calculate_co2_injection",
    "recommend_co2_injection",
    "CO2_MG_PER_M3_PER_PPM",
    "humidity_for_target_vpd",
    "get_score_weight",
    "recommend_light_intensity",
    "recommend_photoperiod",
    "evaluate_heat_stress",
    "evaluate_cold_stress",
    "evaluate_light_stress",
    "evaluate_wind_stress",
    "evaluate_humidity_stress",
    "get_humidity_action",
    "recommend_humidity_action",
    "evaluate_ph_stress",
    "evaluate_stress_conditions",
    "optimize_environment",
    "calculate_environment_metrics",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "EnvironmentGuidelines",
    "StressFlags",
    "WaterQualityInfo",
    "normalize_environment_readings",
    "classify_value_range",
    "compare_environment",
    "generate_environment_alerts",
    "classify_environment_quality",
    "score_overall_environment",
    "summarize_environment",
    "summarize_environment_series",
    "EnvironmentSummary",
]


# Load environment guidelines once. ``load_dataset`` already caches results
_DATA: Dict[str, Any] = load_dataset(DATA_FILE)
_DLI_DATA: Dict[str, Any] = load_dataset(DLI_DATA_FILE)
_VPD_DATA: Dict[str, Any] = load_dataset(VPD_DATA_FILE)
_HEAT_THRESHOLDS: Dict[str, float] = load_dataset(HEAT_DATA_FILE)
_COLD_THRESHOLDS: Dict[str, float] = load_dataset(COLD_DATA_FILE)
_PHOTOPERIOD_DATA: Dict[str, Any] = load_dataset(PHOTOPERIOD_DATA_FILE)
_WIND_THRESHOLDS: Dict[str, float] = load_dataset(WIND_DATA_FILE)
_HUMIDITY_THRESHOLDS: Dict[str, Any] = load_dataset(HUMIDITY_DATA_FILE)
_HUMIDITY_ACTIONS: Dict[str, str] = load_dataset(HUMIDITY_ACTION_FILE)
_SCORE_WEIGHTS: Dict[str, float] = load_dataset(SCORE_WEIGHT_FILE)


def get_score_weight(metric: str) -> float:
    """Return weighting factor for an environment metric."""
    try:
        return float(_SCORE_WEIGHTS.get(metric, 1.0))
    except (TypeError, ValueError):
        return 1.0


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
) -> tuple[float, float] | None:
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


def saturation_vapor_pressure(temp_c: float) -> float:
    """Return saturation vapor pressure (kPa) at ``temp_c``."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def actual_vapor_pressure(temp_c: float, humidity_pct: float) -> float:
    """Return actual vapor pressure (kPa) given temperature and relative humidity."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")
    return saturation_vapor_pressure(temp_c) * humidity_pct / 100


@dataclass
class EnvironmentMetrics:
    """Calculated environmental metrics."""

    vpd: float | None
    dew_point_c: float | None
    heat_index_c: float | None
    absolute_humidity_g_m3: float | None
    et0_mm_day: float | None = None
    eta_mm_day: float | None = None
    transpiration_ml_day: float | None = None

    def as_dict(self) -> Dict[str, float | None]:
        """Return metrics as a regular dictionary."""
        return asdict(self)


@dataclass
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
    photoperiod_hours: float | None = None
    heat_stress: bool | None = None
    cold_stress: bool | None = None
    light_stress: str | None = None
    wind_stress: bool | None = None
    humidity_stress: str | None = None
    ph_stress: str | None = None
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
            "photoperiod_hours": self.photoperiod_hours,
            "heat_stress": self.heat_stress,
            "cold_stress": self.cold_stress,
            "light_stress": self.light_stress,
            "wind_stress": self.wind_stress,
            "humidity_stress": self.humidity_stress,
            "ph_stress": self.ph_stress,
            "quality": self.quality,
            "score": self.score,
            "water_quality": self.water_quality.as_dict() if self.water_quality else None,
        }


@dataclass
class StressFlags:
    """Combined abiotic stress indicators."""

    heat: bool | None
    cold: bool | None
    light: str | None
    wind: bool | None
    humidity: str | None
    ph: str | None

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
            "water_quality": self.water_quality.as_dict() if self.water_quality else None,
        }


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return list_dataset_entries(_DATA)


def get_environmental_targets(
    plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    return get_environment_guidelines(plant_type, stage).as_dict()


def classify_value_range(value: float, bounds: Tuple[float, float]) -> str:
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


def _check_range(value: float, bounds: Tuple[float, float]) -> str | None:
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
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return adjustment suggestions for temperature, humidity, light and CO₂."""

    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return {}

    comparison = compare_environment(current, targets)
    actions: Dict[str, str] = {}
    for key, status in comparison.items():
        if status == "within range":
            continue
        label = ACTION_LABELS.get(key, key)
        actions[label] = "increase" if status == "below range" else "decrease"

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
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> str:
    """Return ``good``, ``fair`` or ``poor`` based on environment score."""

    score = score_environment(current, plant_type, stage)
    if score >= 75:
        return "good"
    if score >= 50:
        return "fair"
    return "poor"


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
    """Return midpoint setpoints for temperature, humidity, light and CO₂."""
    targets = get_environmental_targets(plant_type, stage)
    setpoints: Dict[str, float] = {}
    for key, bounds in targets.items():
        if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
            setpoints[key] = round((bounds[0] + bounds[1]) / 2, 2)
    return setpoints


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

    threshold = _HEAT_THRESHOLDS.get(
        normalize_key(plant_type), _HEAT_THRESHOLDS.get("default")
    )
    if threshold is None:
        return None

    hi = calculate_heat_index(temp_c, humidity_pct)
    return hi >= float(threshold)


def evaluate_cold_stress(
    temp_c: float | None,
    plant_type: str,
) -> bool | None:
    """Return ``True`` if temperature is below the plant cold threshold."""

    if temp_c is None:
        return None

    threshold = _COLD_THRESHOLDS.get(
        normalize_key(plant_type), _COLD_THRESHOLDS.get("default")
    )
    if threshold is None:
        return None

    return temp_c <= float(threshold)


def evaluate_wind_stress(
    wind_m_s: float | None,
    plant_type: str,
) -> bool | None:
    """Return ``True`` if wind speed exceeds the plant threshold."""

    if wind_m_s is None:
        return None

    threshold = _WIND_THRESHOLDS.get(
        normalize_key(plant_type), _WIND_THRESHOLDS.get("default")
    )
    if threshold is None:
        return None

    return wind_m_s >= float(threshold)


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


def recommend_humidity_action(humidity_pct: float | None, plant_type: str) -> str | None:
    """Return humidity adjustment recommendation if outside thresholds."""

    level = evaluate_humidity_stress(humidity_pct, plant_type)
    if level is None:
        return None
    action = get_humidity_action(level)
    return action or None


def evaluate_ph_stress(ph: float | None, plant_type: str, stage: str | None = None) -> str | None:
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
    plant_type: str,
    stage: str | None = None,
) -> StressFlags:
    """Return consolidated stress flags for current conditions."""

    return StressFlags(
        heat=evaluate_heat_stress(temp_c, humidity_pct, plant_type),
        cold=evaluate_cold_stress(temp_c, plant_type),
        light=evaluate_light_stress(dli, plant_type, stage),
        wind=evaluate_wind_stress(wind_m_s, plant_type),
        humidity=evaluate_humidity_stress(humidity_pct, plant_type),
        ph=evaluate_ph_stress(ph, plant_type, stage),
    )


def calculate_dli_series(
    ppfd_values: Iterable[float], interval_hours: float = 1.0
) -> float:
    """Return Daily Light Integral from a sequence of PPFD readings.

    Parameters
    ----------
    ppfd_values: Iterable[float]
        Sequence of PPFD values in µmol⋅m⁻²⋅s⁻¹.
    interval_hours: float
        Time between each measurement in hours. Must be positive.
    """
    if interval_hours <= 0:
        raise ValueError("interval_hours must be positive")

    values = [float(v) for v in ppfd_values]
    if any(v < 0 for v in values):
        raise ValueError("PPFD values must be non-negative")

    total = sum(values)
    dli = total * 3600 * interval_hours / 1_000_000
    return round(dli, 2)


def calculate_vpd_series(
    temp_values: Iterable[float], humidity_values: Iterable[float]
) -> float:
    """Return average VPD from paired temperature and humidity readings."""

    temps = list(temp_values)
    hums = list(humidity_values)
    if len(temps) != len(hums):
        raise ValueError("temperature and humidity readings must have the same length")
    if not temps:
        return 0.0

    total = 0.0
    for t, h in zip(temps, hums):
        total += calculate_vpd(t, h)
    return round(total / len(temps), 3)


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


def get_target_co2(
    plant_type: str, stage: str | None = None
) -> tuple[float, float] | None:
    """Return recommended CO₂ range in ppm for a plant stage."""
    guide = get_environment_guidelines(plant_type, stage)
    return guide.co2_ppm


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


def calculate_environment_metrics(
    temp_c: float | None,
    humidity_pct: float | None,
    *,
    env: Mapping[str, float] | None = None,
    plant_type: str | None = None,
    stage: str | None = None,
) -> EnvironmentMetrics:
    """Return :class:`EnvironmentMetrics` including transpiration when possible."""

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
            "par_w_m2": env.get("par_w_m2") or env.get("par") or env.get("light_ppfd", 0),
            "wind_speed_m_s": env.get("wind_speed_m_s") or env.get("wind_m_s") or env.get("wind", 1.0),
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

    return metrics


def optimize_environment(
    current: Mapping[str, float],
    plant_type: str,
    stage: str | None = None,
    water_test: Mapping[str, float] | None = None,
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

    setpoints = suggest_environment_setpoints(plant_type, stage)
    actions = recommend_environment_adjustments(readings, plant_type, stage)

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
        plant_type,
        stage,
    )

    quality = classify_environment_quality(readings, plant_type, stage)
    score = score_environment(readings, plant_type, stage)

    wq = None
    if water_test is not None:
        rating = water_quality.classify_water_quality(water_test)
        wscore = water_quality.score_water_quality(water_test)
        wq = WaterQualityInfo(rating=rating, score=wscore)

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
        photoperiod_hours=photoperiod_hours,
        heat_stress=stress.heat,
        cold_stress=stress.cold,
        light_stress=stress.light,
        wind_stress=stress.wind,
        humidity_stress=stress.humidity,
        ph_stress=stress.ph,
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
        plant_type,
        stage,
    )

    water_info = None
    if water_test is not None:
        rating = water_quality.classify_water_quality(water_test)
        score = water_quality.score_water_quality(water_test)
        water_info = WaterQualityInfo(rating=rating, score=score)

    summary = EnvironmentSummary(
        quality=classify_environment_quality(readings, plant_type, stage),
        adjustments=recommend_environment_adjustments(readings, plant_type, stage),
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
    include_targets: bool = False,
) -> Dict[str, Any]:
    """Return summary for averaged environment readings.

    When multiple readings are provided they are normalized, averaged and then
    passed to :func:`summarize_environment`.
    """

    iterator = list(series)
    if not iterator:
        avg = {}
    else:
        totals: Dict[str, float] = {}
        count = 0
        for reading in iterator:
            for key, value in normalize_environment_readings(reading).items():
                totals[key] = totals.get(key, 0.0) + float(value)
            count += 1
        avg = {k: v / count for k, v in totals.items()}

    return summarize_environment(
        avg,
        plant_type,
        stage,
        water_test,
        include_targets=include_targets,
    )
