"""Calculate nutrient use efficiency from application and yield logs."""

import os
from typing import Dict, Tuple

from .utils import load_json

# Default storage locations can be overridden with environment variables. This
# makes the module more flexible for testing and deployment scenarios where the
# repository's ``data`` directory is not writable.
NUTRIENT_DIR = os.getenv("HORTICULTURE_NUTRIENT_DIR", "data/nutrients_applied")
YIELD_DIR = os.getenv("HORTICULTURE_YIELD_DIR", "data/yield")

def _load_totals(plant_id: str) -> Tuple[Dict[str, float], float]:
    """Return total nutrients applied (mg) and total yield (g)."""

    path_nutrients = os.path.join(NUTRIENT_DIR, f"{plant_id}.json")
    if not os.path.exists(path_nutrients):
        raise FileNotFoundError(f"No nutrient record found for {plant_id}")

    nutrient_log = load_json(path_nutrients)

    total_applied_mg: Dict[str, float] = {}
    for entry in nutrient_log.get("records", []):
        for k, v in entry.get("nutrients_mg", {}).items():
            total_applied_mg[k] = total_applied_mg.get(k, 0.0) + float(v)

    path_yield = os.path.join(YIELD_DIR, f"{plant_id}.json")
    if not os.path.exists(path_yield):
        raise FileNotFoundError(f"No yield record found for {plant_id}")

    yield_data = load_json(path_yield)

    total_yield_g = sum(float(h.get("yield_grams", 0)) for h in yield_data.get("harvests", []))

    return total_applied_mg, total_yield_g


def calculate_nue(plant_id: str) -> Dict:
    """Return nutrient use efficiency for all nutrients."""

    total_applied_mg, total_yield_g = _load_totals(plant_id)

    nue: Dict[str, float | None] = {}
    for nutrient, mg in total_applied_mg.items():
        g_applied = mg / 1000
        nue[nutrient] = round(total_yield_g / g_applied, 2) if g_applied else None

    return {"plant_id": plant_id, "total_yield_g": total_yield_g, "nue": nue}


def calculate_nue_for_nutrient(plant_id: str, nutrient: str) -> float | None:
    """Return NUE for a single nutrient or ``None`` if data missing."""

    total_applied_mg, total_yield_g = _load_totals(plant_id)
    mg = total_applied_mg.get(nutrient)
    if mg is None:
        return None
    g_applied = mg / 1000
    return round(total_yield_g / g_applied, 2) if g_applied else None
