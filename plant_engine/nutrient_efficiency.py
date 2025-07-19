import os
import json
from typing import Dict

NUTRIENT_DIR = "data/nutrients_applied"
YIELD_DIR = "data/yield"

def calculate_nue(plant_id: str) -> Dict:
    """
    Calculate Nutrient Use Efficiency (NUE) for all nutrients based on applied nutrients vs yield.
    Returns NUE per nutrient as g yield per g nutrient applied.
    """

    # Load total nutrients applied
    path_nutrients = os.path.join(NUTRIENT_DIR, f"{plant_id}.json")
    if not os.path.exists(path_nutrients):
        raise FileNotFoundError(f"No nutrient record found for {plant_id}")

    with open(path_nutrients, "r", encoding="utf-8") as f:
        nutrient_log = json.load(f)

    total_applied_mg = {}
    for entry in nutrient_log.get("records", []):
        for k, v in entry["nutrients_mg"].items():
            total_applied_mg[k] = total_applied_mg.get(k, 0) + v

    # Load total yield
    path_yield = os.path.join(YIELD_DIR, f"{plant_id}.json")
    if not os.path.exists(path_yield):
        raise FileNotFoundError(f"No yield record found for {plant_id}")

    with open(path_yield, "r", encoding="utf-8") as f:
        yield_data = json.load(f)

    total_yield_g = sum(h["yield_grams"] for h in yield_data.get("harvests", []))

    # Calculate NUE
    nue = {}
    for nutrient, mg in total_applied_mg.items():
        g_applied = mg / 1000
        nue[nutrient] = round(total_yield_g / g_applied, 2) if g_applied else None

    return {
        "plant_id": plant_id,
        "total_yield_g": total_yield_g,
        "nue": nue
    }
