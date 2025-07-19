import json
import os
from datetime import datetime
from typing import Dict

GROWTH_DIR = "data/growth"
YIELD_DIR = "data/yield"

def update_growth_index(plant_id: str, env_data: Dict, transpiration_ml: float) -> Dict:
    """
    Update the daily vegetative growth index (VGI) using ETa, PAR, and temp.
    Returns updated VGI stats for the plant.
    """

    date_str = datetime.now().strftime("%Y-%m-%d")
    gdd = max(0, ((env_data["temp_c_max"] + env_data["temp_c_min"]) / 2) - 10)
    par_mj = env_data["par_w_m2"] * 0.0864  # Convert to MJ/m²/day
    eta_factor = transpiration_ml / 1000  # Normalize to liters

    vgi_today = round(gdd * par_mj * eta_factor, 2)

    os.makedirs(GROWTH_DIR, exist_ok=True)
    path = os.path.join(GROWTH_DIR, f"{plant_id}.json")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            growth_data = json.load(f)
    else:
        growth_data = {}

    growth_data[date_str] = {
        "vgi": vgi_today,
        "gdd": gdd,
        "par": par_mj,
        "et_liters": eta_factor
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(growth_data, f, indent=2)

    cumulative_vgi = round(sum(day["vgi"] for day in growth_data.values()), 2)

    return {
        "plant_id": plant_id,
        "vgi_today": vgi_today,
        "vgi_total": cumulative_vgi,
        "days_tracked": len(growth_data)
    }
