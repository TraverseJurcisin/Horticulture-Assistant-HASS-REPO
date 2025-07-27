"""Compute water use efficiency metrics."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Dict

from .utils import load_json, load_dataset, normalize_key
from .water_usage import estimate_cycle_total_use

TARGET_FILE = "water_efficiency_targets.json"
YIELD_DIR = Path("data/yield")

__all__ = [
    "calculate_wue",
    "evaluate_wue",
]


def _load_yield(plant_id: str) -> float:
    path = YIELD_DIR / f"{plant_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No yield record found for {plant_id}")
    data = load_json(path)
    return sum(float(h.get("yield_grams", 0)) for h in data.get("harvests", []))


def calculate_wue(plant_id: str, plant_type: str) -> float:
    """Return water use efficiency (g/L) for ``plant_id``."""
    total_yield_g = _load_yield(plant_id)
    usage_ml = estimate_cycle_total_use(plant_type)
    if usage_ml <= 0:
        return 0.0
    return round(total_yield_g / (usage_ml / 1000.0), 2)


def evaluate_wue(wue: float, plant_type: str, tolerance: float = 0.1) -> Dict[str, float | str]:
    """Return assessment of WUE versus target for ``plant_type``."""
    targets = load_dataset(TARGET_FILE)
    target = float(targets.get(normalize_key(plant_type), 0))
    lower = target * (1 - tolerance)
    upper = target * (1 + tolerance)
    if target <= 0:
        status = "no target"
    elif wue < lower:
        status = "below target"
    elif wue > upper:
        status = "above target"
    else:
        status = "within target"
    return {"wue": wue, "target": target, "status": status}
