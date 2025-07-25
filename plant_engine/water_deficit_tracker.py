"""Track and summarize plant water balance over time."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, Any

STORAGE_PATH = "data/water_balance"
MAX_LOG_DAYS = 14  # for rolling average or ET smoothing (optional)


@dataclass(slots=True)
class WaterBalance:
    """Summary of the current water balance status."""

    plant_id: str
    date: str
    ml_available: float
    depletion_pct: float
    mad_crossed: bool
    raw_ml: float
    taw_ml: float
    mad_pct: float

    def as_dict(self) -> Dict[str, Any]:
        """Return a serializable dictionary representation."""
        return asdict(self)

    def __getitem__(self, item: str) -> Any:  # convenience for legacy dict access
        return getattr(self, item)




def update_water_balance(
    plant_id: str,
    irrigation_ml: float,
    transpiration_ml: float,
    storage_path: str = STORAGE_PATH,
    *,
    rootzone_ml: Optional[float] = None,
    mad_pct: float = 0.5,
) -> WaterBalance:
    """Update and return the daily water balance for a plant.

    Parameters
    ----------
    plant_id : str
        Identifier for the plant.
    irrigation_ml : float
        Water applied today in milliliters.
    transpiration_ml : float
        Estimated transpiration loss for today in milliliters.
    storage_path : str, optional
        Directory for water balance logs.
    rootzone_ml : float, optional
        Total available water (TAW) of the root zone in milliliters.
        If not provided a default of 3000 mL is used.
    mad_pct : float, optional
        Management allowed depletion as a fraction of TAW.
    """

    os.makedirs(storage_path, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(storage_path, f"{plant_id}.json")

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
    if rootzone_ml is None:
        rootzone_ml = 3000  # Default if not provided
    raw_ml = rootzone_ml * mad_pct

    available_ml = max(0, min(cumulative_ml, rootzone_ml))
    depletion_pct = round(1.0 - (available_ml / rootzone_ml), 3)
    mad_crossed = depletion_pct >= mad_pct

    # Package result
    summary = WaterBalance(
        plant_id=plant_id,
        date=today,
        ml_available=round(available_ml, 1),
        depletion_pct=depletion_pct,
        mad_crossed=mad_crossed,
        raw_ml=round(raw_ml, 1),
        taw_ml=rootzone_ml,
        mad_pct=mad_pct,
    )

    # Write updated history
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return summary


def load_water_balance(plant_id: str, storage_path: str = STORAGE_PATH) -> Dict[str, Any]:
    """Return the logged water balance history for ``plant_id``."""
    file_path = os.path.join(storage_path, f"{plant_id}.json")
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = ["update_water_balance", "load_water_balance", "WaterBalance"]

