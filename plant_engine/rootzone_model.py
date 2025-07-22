"""Root zone modeling utilities."""
from __future__ import annotations

import math

from dataclasses import dataclass, asdict
from typing import Dict, Mapping, Any

from .utils import load_dataset, normalize_key

DEFAULT_AREA_CM2 = 900  # ~30×30 cm surface area

SOIL_DATA_FILE = "soil_texture_parameters.json"

# cached dataset for soil parameters
_SOIL_DATA: Dict[str, Dict[str, Any]] = load_dataset(SOIL_DATA_FILE)

__all__ = [
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "get_soil_parameters",
    "RootZone",
]


def get_soil_parameters(texture: str) -> Dict[str, float]:
    """Return soil parameters for ``texture`` if available."""
    return _SOIL_DATA.get(normalize_key(texture), {})


def estimate_rootzone_depth(
    plant_profile: Mapping[str, float],
    growth: Mapping[str, float],
) -> float:
    """Estimate root depth (cm) using a logistic growth curve."""
    max_depth_cm = plant_profile.get("max_root_depth_cm", 30)
    growth_index = growth.get("vgi_total", 0)

    midpoint = 60
    k = 0.08

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
