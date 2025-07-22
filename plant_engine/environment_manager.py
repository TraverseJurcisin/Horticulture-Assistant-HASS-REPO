"""Utilities for environment targets and optimization helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, Mapping, Tuple, Iterable

from .utils import load_dataset
from . import ph_manager

DATA_FILE = "environment_guidelines.json"
DLI_DATA_FILE = "light_dli_guidelines.json"

# map of dataset keys to human readable labels used when recommending
# adjustments. defined here once to avoid recreating each call.
ACTION_LABELS = {
    "temp_c": "temperature",
    "humidity_pct": "humidity",
    "light_ppfd": "light",
    "co2_ppm": "co2",
}


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
    "calculate_dli",
    "photoperiod_for_target_dli",
    "calculate_dli_series",
    "get_target_dli",
    "humidity_for_target_vpd",
    "optimize_environment",
    "calculate_environment_metrics",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
]


# Load environment guidelines once. ``load_dataset`` already caches results
_DATA: Dict[str, Any] = load_dataset(DATA_FILE)
_DLI_DATA: Dict[str, Any] = load_dataset(DLI_DATA_FILE)


def _norm(key: str) -> str:
    """Normalize keys for case-insensitive lookups."""
    return key.lower()


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
    photoperiod_hours: float | None = None

    def as_dict(self) -> Dict[str, Any]:
        """Return the optimization result as a serializable dictionary."""
        return {
            "setpoints": self.setpoints,
            "adjustments": self.adjustments,
            "vpd": self.metrics.vpd,
            "dew_point_c": self.metrics.dew_point_c,
            "heat_index_c": self.metrics.heat_index_c,
            "ph_setpoint": self.ph_setpoint,
            "ph_action": self.ph_action,
            "target_dli": self.target_dli,
            "photoperiod_hours": self.photoperiod_hours,
        }


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return sorted(_DATA.keys())


def get_environmental_targets(
    plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    data = _DATA.get(_norm(plant_type), {})
    if stage:
        stage = _norm(stage)
        if stage in data:
            return data[stage]
    return data.get("optimal", {})


def _check_range(value: float, bounds: Tuple[float, float]) -> str | None:
    """Return 'increase' or 'decrease' if value is outside ``bounds``."""

    low, high = bounds
    if value < low:
        return "increase"
    if value > high:
        return "decrease"
    return None


def recommend_environment_adjustments(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, str]:
    """Return adjustment suggestions for temperature, humidity, light and CO₂."""
    targets = get_environmental_targets(plant_type, stage)
    actions: Dict[str, str] = {}

    if not targets:
        return actions

    for key, label in ACTION_LABELS.items():
        if key in targets and key in current:
            suggestion = _check_range(current[key], tuple(targets[key]))
            if suggestion:
                actions[label] = suggestion

    return actions


def score_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> float:
    """Return a 0-100 score representing how close ``current`` is to targets."""
    targets = get_environmental_targets(plant_type, stage)
    if not targets:
        return 0.0

    score = 0.0
    count = 0
    for key, bounds in targets.items():
        if key not in current or not isinstance(bounds, (list, tuple)):
            continue
        low, high = bounds
        val = current[key]
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
        - 0.00683783 * temp_f ** 2
        - 0.05481717 * rh ** 2
        + 0.00122874 * temp_f ** 2 * rh
        + 0.00085282 * temp_f * rh ** 2
        - 0.00000199 * temp_f ** 2 * rh ** 2
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


def calculate_dli_series(ppfd_values: Iterable[float], interval_hours: float = 1.0) -> float:
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


def get_target_dli(plant_type: str, stage: str | None = None) -> tuple[float, float] | None:
    """Return recommended DLI range for ``plant_type`` and ``stage`` if available."""
    data = _DLI_DATA.get(_norm(plant_type), {})
    if stage:
        stage = _norm(stage)
        if stage in data:
            vals = data[stage]
            if len(vals) == 2:
                return tuple(vals)
    vals = data.get("optimal")
    if isinstance(vals, list) and len(vals) == 2:
        return tuple(vals)
    return None


def calculate_environment_metrics(
    temp_c: float | None, humidity_pct: float | None
) -> EnvironmentMetrics:
    """Return :class:`EnvironmentMetrics` if inputs are provided."""

    if temp_c is None or humidity_pct is None:
        return EnvironmentMetrics(None, None, None)

    return EnvironmentMetrics(
        vpd=calculate_vpd(temp_c, humidity_pct),
        dew_point_c=calculate_dew_point(temp_c, humidity_pct),
        heat_index_c=calculate_heat_index(temp_c, humidity_pct),
    )


def optimize_environment(
    current: Mapping[str, float], plant_type: str, stage: str | None = None
) -> Dict[str, object]:
    """Return optimized environment data for a plant.

    The result includes midpoint setpoints, adjustment suggestions, Vapor
    Pressure Deficit (VPD), dew point and heat index when temperature and
    humidity values are supplied. This helper consolidates several utilities for
    convenience when automating greenhouse controls.
    """

    setpoints = suggest_environment_setpoints(plant_type, stage)
    actions = recommend_environment_adjustments(current, plant_type, stage)

    metrics = calculate_environment_metrics(
        current.get("temp_c"), current.get("humidity_pct")
    )
    # pH integration
    ph_set = ph_manager.recommended_ph_setpoint(plant_type, stage)
    ph_act = None
    if "ph" in current and ph_set is not None:
        ph_act = ph_manager.recommend_ph_adjustment(current["ph"], plant_type, stage)

    target_dli = get_target_dli(plant_type, stage)
    photoperiod_hours = None
    if target_dli and "light_ppfd" in current:
        mid_target = sum(target_dli) / 2
        photoperiod_hours = photoperiod_for_target_dli(mid_target, current["light_ppfd"])

    result = EnvironmentOptimization(
        setpoints,
        actions,
        metrics,
        ph_setpoint=ph_set,
        ph_action=ph_act,
        target_dli=target_dli,
        photoperiod_hours=photoperiod_hours,
    )
    return result.as_dict()
