from typing import Dict
import math

DEFAULT_DENSITY = 1.2  # g/cm³ typical for loose potting mix
DEFAULT_AREA_CM2 = 900  # ~30 cm x 30 cm surface area

def estimate_rootzone_depth(plant_profile: Dict, growth: Dict) -> float:
    """
    Estimate root depth (cm) using VGI or age-based growth curve.
    Uses sigmoid: max_depth / (1 + e^(-k*(vgi - midpoint)))
    """

    max_depth_cm = plant_profile.get("max_root_depth_cm", 30)
    growth_index = growth.get("vgi_total", 0)

    # Sigmoid parameters
    midpoint = 60
    k = 0.08

    depth = max_depth_cm / (1 + math.exp(-k * (growth_index - midpoint)))
    return round(depth, 2)


def estimate_water_capacity(root_depth_cm: float, area_cm2: float = DEFAULT_AREA_CM2, bd: float = DEFAULT_DENSITY) -> Dict:
    """
    Estimate TAW, RAW, and MAD thresholds.
    Assumes 20% volumetric water content at field capacity.
    """
    volume_cm3 = root_depth_cm * area_cm2
    water_capacity_ml = volume_cm3 * 0.20  # 20% FC
    taw = water_capacity_ml
    raw = taw * 0.5  # MAD = 50%
    return {
        "root_depth_cm": root_depth_cm,
        "root_volume_cm3": volume_cm3,
        "total_available_water_ml": round(taw, 1),
        "readily_available_water_ml": round(raw, 1),
        "mad_pct": 0.5
    }
