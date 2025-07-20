import json
import os
from datetime import datetime
from typing import Dict

STORAGE_PATH = "data/water_balance"
MAX_LOG_DAYS = 14  # for rolling average or ET smoothing (optional)


def update_water_balance(plant_id: str, irrigation_ml: float, transpiration_ml: float) -> Dict:
    """
    Update the water balance file for a plant.
    Adds today's irrigation and ET loss to cumulative water availability.
    Returns new status dictionary (ml_available, % depletion, etc.).
    """

    os.makedirs(STORAGE_PATH, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(STORAGE_PATH, f"{plant_id}.json")

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = {}

    history[today] = {
        "irrigated": irrigation_ml,
        "et": transpiration_ml
    }

    # Only keep recent history
    sorted_keys = sorted(history.keys())[-MAX_LOG_DAYS:]
    history = {k: history[k] for k in sorted_keys}

    # Calculate cumulative water balance
    cumulative_ml = 0
    for day in sorted_keys:
        entry = history[day]
        cumulative_ml += entry["irrigated"] - entry["et"]

    # Root zone capacity from profile
    rootzone_ml = 3000  # Example default if not dynamically loaded
    mad_pct = 0.5       # 50% depletion allowable

    available_ml = max(0, min(cumulative_ml, rootzone_ml))
    depletion_pct = round(1.0 - (available_ml / rootzone_ml), 3)
    mad_crossed = depletion_pct >= mad_pct

    # Package result
    summary = {
        "plant_id": plant_id,
        "date": today,
        "ml_available": round(available_ml, 1),
        "depletion_pct": depletion_pct,
        "mad_crossed": mad_crossed
    }

    # Write updated history
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return summary
