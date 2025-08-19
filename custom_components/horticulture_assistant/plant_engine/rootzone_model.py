"""Root zone modeling utilities."""
from __future__ import annotations

import math

from dataclasses import dataclass, asdict
from typing import Dict, Mapping, Any

from .utils import load_dataset, normalize_key

DEFAULT_AREA_CM2 = 900  # ~30×30 cm surface area

SOIL_DATA_FILE = "soil/soil_texture_parameters.json"
ROOT_DEPTH_DATA_FILE = "root/root_depth_guidelines.json"  # average max root depth per crop
INFILTRATION_FILE = "soil/soil_infiltration_rates.json"
GROWTH_PARAM_FILE = "root/root_growth_parameters.json"

# cached dataset for soil parameters
_SOIL_DATA: Dict[str, Dict[str, Any]] = load_dataset(SOIL_DATA_FILE)
_ROOT_DEPTH_DATA: Dict[str, float] = load_dataset(ROOT_DEPTH_DATA_FILE)
_INFILTRATION_DATA: Dict[str, float] = load_dataset(INFILTRATION_FILE)
_GROWTH_PARAMS: Dict[str, Mapping[str, float]] = load_dataset(GROWTH_PARAM_FILE)

__all__ = [
    "estimate_rootzone_depth",
    "get_growth_curve_params",
    "get_default_root_depth",
    "estimate_water_capacity",
    "calculate_remaining_water",
    "soil_moisture_pct",
    "get_soil_parameters",
    "get_infiltration_rate",
    "estimate_infiltration_time",
    "calculate_infiltration_volume",
    "RootZone",
]


def get_soil_parameters(texture: str) -> Dict[str, float]:
    """Return soil parameters for ``texture`` if available.

    The returned mapping always contains the ``field_capacity`` and
    ``mad_fraction`` values when known.  If infiltration rate data is
    available it is included under ``infiltration_rate_mm_hr`` so callers
    can avoid a second lookup.
    """

    key = normalize_key(texture)
    params = dict(_SOIL_DATA.get(key, {}))
    infil = _INFILTRATION_DATA.get(key)
    try:
        if infil is not None:
            params.setdefault("infiltration_rate_mm_hr", float(infil))
    except (TypeError, ValueError):
        pass
    return params


def get_infiltration_rate(texture: str) -> float | None:
    """Return infiltration rate (mm/hr) for a soil texture if known."""
    rate = _INFILTRATION_DATA.get(normalize_key(texture))
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):
        return None


def get_default_root_depth(plant_type: str) -> float:
    """Return default maximum root depth for ``plant_type`` in centimeters."""

    depth = _ROOT_DEPTH_DATA.get(normalize_key(plant_type))
    if depth is None:
        return 30.0
    try:
        return float(depth)
    except (TypeError, ValueError):
        return 30.0


def get_growth_curve_params(plant_type: str) -> tuple[float, float]:
    """Return logistic growth parameters ``(midpoint, k)`` for a plant type."""

    data = _GROWTH_PARAMS.get(normalize_key(plant_type)) or {}
    try:
        midpoint = float(data.get("midpoint", _GROWTH_PARAMS.get("default", {}).get("midpoint", 60)))
    except (TypeError, ValueError):
        midpoint = 60.0
    try:
        k = float(data.get("k", _GROWTH_PARAMS.get("default", {}).get("k", 0.08)))
    except (TypeError, ValueError):
        k = 0.08
    return midpoint, k


def estimate_rootzone_depth(
    plant_profile: Mapping[str, float],
    growth: Mapping[str, float],
) -> float:
    """Estimate root depth (cm) using a logistic growth curve."""
    plant_type = plant_profile.get("plant_type", "")
    max_depth_cm = plant_profile.get("max_root_depth_cm")
    if max_depth_cm is None:
        max_depth_cm = get_default_root_depth(plant_type)

    growth_index = growth.get("vgi_total", 0)
    midpoint, k = get_growth_curve_params(plant_type)

    depth = max_depth_cm / (1 + math.exp(-k * (growth_index - midpoint)))
    return round(depth, 2)

@dataclass
class RootZone:
    """Container for root zone capacity estimates."""

    root_depth_cm: float
    root_volume_cm3: float
    total_available_water_ml: float
    readily_available_water_ml: float
    field_capacity_pct: float = 0.20
    mad_pct: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def calculate_remaining_water(
        self,
        available_ml: float,
        *,
        irrigation_ml: float = 0.0,
        et_ml: float = 0.0,
    ) -> float:
        """Return updated water volume after irrigation and ET losses."""

        if any(x < 0 for x in (available_ml, irrigation_ml, et_ml)):
            raise ValueError("Volumes must be non-negative")

        new_vol = available_ml + irrigation_ml - et_ml
        new_vol = min(new_vol, self.total_available_water_ml)
        return round(max(new_vol, 0.0), 1)

    def moisture_pct(self, available_ml: float) -> float:
        """Return current soil moisture percentage."""

        if available_ml < 0:
            raise ValueError("available_ml must be non-negative")

        if self.total_available_water_ml <= 0:
            return 0.0

        pct = (available_ml / self.total_available_water_ml) * 100
        return round(min(max(pct, 0.0), 100.0), 1)


def estimate_water_capacity(
    root_depth_cm: float,
    area_cm2: float = DEFAULT_AREA_CM2,
    *,
    field_capacity: float | None = None,
    mad_fraction: float | None = None,
    texture: str | None = None,
) -> RootZone:
    """Return root zone water capacity estimates.

    Parameters
    ----------
    root_depth_cm : float
        Estimated root depth in centimeters.
    area_cm2 : float, optional
        Soil surface area in square centimeters.
    field_capacity : float, optional
        Fractional water content at field capacity (0-1).
    mad_fraction : float, optional
        Fractional management allowed depletion (0-1).
    texture : str, optional
        Soil texture key used to look up defaults from
        :data:`soil_texture_parameters.json` when ``field_capacity`` or
        ``mad_fraction`` are omitted.
    """
    if field_capacity is None or mad_fraction is None:
        if texture:
            params = get_soil_parameters(texture)
            if field_capacity is None:
                field_capacity = params.get("field_capacity", 0.20)
            if mad_fraction is None:
                mad_fraction = params.get("mad_fraction", 0.5)
        if field_capacity is None:
            field_capacity = 0.20
        if mad_fraction is None:
            mad_fraction = 0.5

    volume_cm3 = root_depth_cm * area_cm2
    water_capacity_ml = volume_cm3 * field_capacity
    taw = water_capacity_ml
    raw = taw * mad_fraction
    return RootZone(
        root_depth_cm=root_depth_cm,
        root_volume_cm3=volume_cm3,
        total_available_water_ml=round(taw, 1),
        readily_available_water_ml=round(raw, 1),
        field_capacity_pct=field_capacity,
        mad_pct=mad_fraction,
    )


def estimate_infiltration_time(
    volume_ml: float,
    area_m2: float,
    texture: str | None = None,
    *,
    infiltration_rate: float | None = None,
) -> float | None:
    """Return hours required for ``volume_ml`` to infiltrate.

    ``texture`` is used to look up the infiltration rate from
    :data:`soil_infiltration_rates.json` if ``infiltration_rate`` is not
    provided.  This allows callers to supply a custom rate without a dataset
    lookup.  ``None`` is returned when no rate information is available.
    """

    if volume_ml < 0 or area_m2 <= 0:
        raise ValueError("volume_ml must be non-negative and area_m2 positive")

    rate = infiltration_rate
    if rate is None and texture is not None:
        rate = get_infiltration_rate(texture)
    if rate is None or rate <= 0:
        return None

    depth_mm = volume_ml / 1000 / area_m2
    hours = depth_mm / rate
    return round(hours, 2)


def calculate_infiltration_volume(
    time_hr: float,
    area_m2: float,
    texture: str | None = None,
    *,
    infiltration_rate: float | None = None,
) -> float | None:
    """Return water volume (mL) infiltrated over ``time_hr`` hours.

    The ``texture`` parameter behaves the same as in
    :func:`estimate_infiltration_time`.  ``None`` is returned when no
    infiltration rate information is available.
    """

    if time_hr < 0 or area_m2 <= 0:
        raise ValueError("time_hr must be non-negative and area_m2 positive")

    rate = infiltration_rate
    if rate is None and texture is not None:
        rate = get_infiltration_rate(texture)
    if rate is None or rate <= 0:
        return None

    depth_mm = rate * time_hr
    volume_ml = depth_mm * area_m2 * 1000
    return round(volume_ml, 1)


def calculate_remaining_water(
    rootzone: RootZone,
    available_ml: float,
    *,
    irrigation_ml: float = 0.0,
    et_ml: float = 0.0,
) -> float:
    """Return updated available water volume within the root zone."""

    return rootzone.calculate_remaining_water(
        available_ml, irrigation_ml=irrigation_ml, et_ml=et_ml
    )


def soil_moisture_pct(rootzone: RootZone, available_ml: float) -> float:
    """Return current soil moisture as a percentage of capacity."""

    return rootzone.moisture_pct(available_ml)
