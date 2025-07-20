"""Root zone modeling utilities."""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, Mapping

DEFAULT_DENSITY = 1.2  # g/cm³, typical loose potting mix
DEFAULT_AREA_CM2 = 900  # ~30×30 cm surface area


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
    mad_pct: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


def estimate_water_capacity(
    root_depth_cm: float,
    area_cm2: float = DEFAULT_AREA_CM2,
    bulk_density: float = DEFAULT_DENSITY,
) -> RootZone:
    """Return TAW and RAW estimates based on root depth and soil properties."""
    volume_cm3 = root_depth_cm * area_cm2
    water_capacity_ml = volume_cm3 * 0.20  # field capacity ~20% VWC
    taw = water_capacity_ml
    raw = taw * 0.5  # management allowed depletion 50%
    return RootZone(
        root_depth_cm=root_depth_cm,
        root_volume_cm3=volume_cm3,
        total_available_water_ml=round(taw, 1),
        readily_available_water_ml=round(raw, 1),
    )
