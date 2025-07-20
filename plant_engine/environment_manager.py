"""Utilities for retrieving environment guidelines and computing adjustments."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from .utils import load_dataset

DATA_FILE = "environment_guidelines.json"



# Load environment guidelines once. ``load_dataset`` already caches results
_DATA: Dict[str, Any] = load_dataset(DATA_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with available environment data."""
    return sorted(_DATA.keys())


def get_environmental_targets(
    plant_type: str, stage: str | None = None
) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    data = _DATA.get(plant_type, {})
    if stage:
        stage = stage.lower()
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

    mappings = {
        "temp_c": "temperature",
        "humidity_pct": "humidity",
        "light_ppfd": "light",
        "co2_ppm": "co2",
    }

    for key, label in mappings.items():
        if key in targets and key in current:
            suggestion = _check_range(current[key], tuple(targets[key]))
            if suggestion:
                actions[label] = suggestion

    return actions


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
    """Return Vapor Pressure Deficit (kPa) using a simple approximation."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")

    import math

    es = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * humidity_pct / 100
    vpd = es - ea
    return round(vpd, 3)


def calculate_dew_point(temp_c: float, humidity_pct: float) -> float:
    """Return dew point temperature (°C) using the Magnus formula."""
    if not 0 <= humidity_pct <= 100:
        raise ValueError("humidity_pct must be between 0 and 100")

    import math

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

    temp = current.get("temp_c")
    humidity = current.get("humidity_pct")

    vpd = None
    dew_point = None
    heat_index = None
    if temp is not None and humidity is not None:
        vpd = calculate_vpd(temp, humidity)
        dew_point = calculate_dew_point(temp, humidity)
        heat_index = calculate_heat_index(temp, humidity)

    return {
        "setpoints": setpoints,
        "adjustments": actions,
        "vpd": vpd,
        "dew_point_c": dew_point,
        "heat_index_c": heat_index,
    }
