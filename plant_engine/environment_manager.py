"""Utilities for environment targets and optimization helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Mapping, Tuple, Iterable

from .utils import load_dataset, normalize_key
from . import ph_manager

DATA_FILE = "environment_guidelines.json"
DLI_DATA_FILE = "light_dli_guidelines.json"
VPD_DATA_FILE = "vpd_guidelines.json"
HEAT_DATA_FILE = "heat_stress_thresholds.json"
COLD_DATA_FILE = "cold_stress_thresholds.json"

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
    "temp_c": ["temp_c", "temperature", "temp"],
    "humidity_pct": ["humidity_pct", "humidity", "rh", "rh_pct"],
    "light_ppfd": ["light_ppfd", "light", "par", "par_w_m2"],
    "co2_ppm": ["co2_ppm", "co2"],
    "ec": ["ec", "EC"],
}

# reverse mapping for constant time alias lookups
_ALIAS_MAP: Dict[str, str] = {
    alias: canonical
    for canonical, aliases in ENV_ALIASES.items()
    for alias in aliases
}


def normalize_environment_readings(readings: Mapping[str, float]) -> Dict[str, float]:
    """Return ``readings`` with keys mapped to canonical environment names."""

    normalized: Dict[str, float] = {}
    for key, value in readings.items():
        canonical = _ALIAS_MAP.get(key, key)
        try:
            normalized[canonical] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


__all__ = [
    "list_supported_plants",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "score_environment",
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
    "calculate_dli_series",
    "get_target_dli",
    "get_target_vpd",
    "humidity_for_target_vpd",
    "recommend_photoperiod",
    "evaluate_heat_stress",
    "evaluate_cold_stress",
    "optimize_environment",
    "calculate_environment_metrics",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "normalize_environment_readings",
    "compare_environment",
    "generate_environment_alerts",
    "classify_environment_quality",
    "summarize_environment",
    "EnvironmentSummary",
]


# Load environment guidelines once. ``load_dataset`` already caches results
_DATA: Dict[str, Any] = load_dataset(DATA_FILE)
_DLI_DATA: Dict[str, Any] = load_dataset(DLI_DATA_FILE)
_VPD_DATA: Dict[str, Any] = load_dataset(VPD_DATA_FILE)
_HEAT_THRESHOLDS: Dict[str, float] = load_dataset(HEAT_DATA_FILE)
_COLD_THRESHOLDS: Dict[str, float] = load_dataset(COLD_DATA_FILE)


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
    photoperiod_hours: float | None = None
    heat_stress: bool | None = None
    cold_stress: bool | None = None

    def as_dict(self) -> Dict[str, Any]:
        """Return the optimization result as a serializable dictionary."""
        return {
            "setpoints": self.setpoints,
            "adjustments": self.adjustments,
            "vpd": self.metrics.vpd,
            "dew_point_c": self.metrics.dew_point_c,
            "heat_index_c": self.metrics.heat_index_c,
            "absolute_humidity_g_m3": self.metrics.absolute_humidity_g_m3,
            "ph_setpoint": self.ph_setpoint,
            "ph_action": self.ph_action,
            "target_dli": self.target_dli,
            "target_vpd": self.target_vpd,
            "photoperiod_hours": self.photoperiod_hours,
            "heat_stress": self.heat_stress,
        "cold_stress": self.cold_stress,
        }


@dataclass
class EnvironmentSummary:
    """High level summary of current environmental conditions."""

    quality: str
    adjustments: Dict[str, str]
    metrics: EnvironmentMetrics

    def as_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality,
            "adjustments": self.adjustments,
            "metrics": self.metrics.as_dict(),
        }


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return sorted(_DATA.keys())


def get_environmental_targets(
    plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    return _lookup_stage_data(_DATA, plant_type, stage)


def _check_range(value: float, bounds: Tuple[float, float]) -> str | None:
    """Return 'increase' or 'decrease' if value is outside ``bounds``."""

    low, high = bounds
    if value < low:
        return "increase"
    if value > high:
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

        if val < low:
            results[key] = "below range"
        elif val > high:
            results[key] = "above range"
        else:
            results[key] = "within range"

    return results


def recommend_environment_adjustments(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return adjustment suggestions for temperature, humidity, light and CO₂."""
    targets = get_environmental_targets(plant_type, stage)
    actions: Dict[str, str] = {}

    if not targets:
        return actions

    readings = normalize_environment_readings(current)
    for key, label in ACTION_LABELS.items():
        if key in targets and key in readings:
            suggestion = _check_range(readings[key], tuple(targets[key]))
            if suggestion:
                actions[label] = suggestion

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


def score_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> float:
    """Return a 0-100 score representing how close ``current`` is to targets."""
    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return 0.0

    readings = normalize_environment_readings(current)
    score = 0.0
    count = 0
    for key, bounds in targets.items():
        if key not in readings or not isinstance(bounds, (list, tuple)):
            continue
        low, high = bounds
        val = readings[key]
        width = high - low
        if width <= 0:
            continue
        if low <= val <= high:
            score += 1
        elif val < low:
            score += max(0.0, 1 - (low - val) / width)
        else:
            score += max(0.0, 1 - (val - high) / width)
        count += 1

    if count == 0:
        return 0.0
    return round((score / count) * 100, 1)


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
    total = 0.0
    for val in ppfd_values:
        if val < 0:
            raise ValueError("PPFD values must be non-negative")
        total += val * 3600 * interval_hours
    return round(total / 1_000_000, 2)


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


def calculate_environment_metrics(
    temp_c: float | None, humidity_pct: float | None
) -> EnvironmentMetrics:
    """Return :class:`EnvironmentMetrics` if inputs are provided."""

    if temp_c is None or humidity_pct is None:
        return EnvironmentMetrics(None, None, None, None)

    return EnvironmentMetrics(
        vpd=calculate_vpd(temp_c, humidity_pct),
        dew_point_c=calculate_dew_point(temp_c, humidity_pct),
        heat_index_c=calculate_heat_index(temp_c, humidity_pct),
        absolute_humidity_g_m3=calculate_absolute_humidity(temp_c, humidity_pct),
    )


def optimize_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, object]:
    """Return optimized environment data for a plant.

    The result includes midpoint setpoints, adjustment suggestions and key
    environmental metrics such as Vapor Pressure Deficit (VPD), dew point,
    heat index and absolute humidity when temperature and humidity readings are
    available. It also flags potential heat stress based on
    :data:`heat_stress_thresholds.json`. If target DLI or VPD ranges are
    defined in the datasets they are also included. This helper consolidates
    several utilities for convenience when automating greenhouse controls.
    """

    readings = normalize_environment_readings(current)

    setpoints = suggest_environment_setpoints(plant_type, stage)
    actions = recommend_environment_adjustments(readings, plant_type, stage)

    metrics = calculate_environment_metrics(
        readings.get("temp_c"), readings.get("humidity_pct")
    )

    heat_stress = evaluate_heat_stress(
        readings.get("temp_c"), readings.get("humidity_pct"), plant_type
    )
    cold_stress = evaluate_cold_stress(readings.get("temp_c"), plant_type)
    # pH integration
    ph_set = ph_manager.recommended_ph_setpoint(plant_type, stage)
    ph_act = None
    if "ph" in readings and ph_set is not None:
        ph_act = ph_manager.recommend_ph_adjustment(readings["ph"], plant_type, stage)

    target_dli = get_target_dli(plant_type, stage)
    target_vpd = get_target_vpd(plant_type, stage)
    photoperiod_hours = None
    if target_dli and "light_ppfd" in readings:
        mid_target = sum(target_dli) / 2
        photoperiod_hours = photoperiod_for_target_dli(
            mid_target, readings["light_ppfd"]
        )

    result = EnvironmentOptimization(
        setpoints,
        actions,
        metrics,
        ph_setpoint=ph_set,
        ph_action=ph_act,
        target_dli=target_dli,
        target_vpd=target_vpd,
        photoperiod_hours=photoperiod_hours,
        heat_stress=heat_stress,
        cold_stress=cold_stress,
    )
    return result.as_dict()


def summarize_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return combined quality rating, adjustments and metrics."""

    readings = normalize_environment_readings(current)

    summary = EnvironmentSummary(
        quality=classify_environment_quality(readings, plant_type, stage),
        adjustments=recommend_environment_adjustments(readings, plant_type, stage),
        metrics=calculate_environment_metrics(
            readings.get("temp_c"), readings.get("humidity_pct")
        ),
    )
    return summary.as_dict()
