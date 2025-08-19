"""Nutrient use efficiency helpers.

This module calculates nutrient use efficiency (NUE) from recorded nutrient
applications and crop yield logs.  It also compares computed values to
recommended targets loaded from :data:`nutrient_efficiency_targets.json`.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple, Mapping, Any

from .utils import load_json, load_dataset, normalize_key

__all__ = [
    "calculate_nue",
    "calculate_nue_for_nutrient",
    "evaluate_nue",
    "evaluate_plant_nue",
]

# Dataset containing NUE targets per crop
TARGET_FILE = "nutrients/nutrient_efficiency_targets.json"

# Default storage locations can be overridden with environment variables. This
# makes the module more flexible for testing and deployment scenarios where the
# repository's ``data`` directory is not writable.
NUTRIENT_DIR = os.getenv("HORTICULTURE_NUTRIENT_DIR", "data/nutrients_applied")
YIELD_DIR = os.getenv("HORTICULTURE_YIELD_DIR", "data/yield")

def _load_totals(plant_id: str) -> Tuple[Dict[str, float], float]:
    """Return total nutrients applied (mg) and total yield (g)."""

    nutrient_dir = Path(NUTRIENT_DIR)
    yield_dir = Path(YIELD_DIR)

    path_nutrients = nutrient_dir / f"{plant_id}.json"
    if not path_nutrients.exists():
        raise FileNotFoundError(f"No nutrient record found for {plant_id}")

    nutrient_log = load_json(path_nutrients)

    total_applied_mg: Dict[str, float] = {}
    for entry in nutrient_log.get("records", []):
        for k, v in entry.get("nutrients_mg", {}).items():
            total_applied_mg[k] = total_applied_mg.get(k, 0.0) + float(v)

    path_yield = yield_dir / f"{plant_id}.json"
    if not path_yield.exists():
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


@lru_cache(maxsize=None)
def _load_targets(plant_type: str) -> Dict[str, float]:
    """Return NUE targets for ``plant_type`` from the dataset.

    Results are cached so repeated evaluations avoid disk access. Call
    :func:`functools.lru_cache`.cache_clear() on this function if underlying
    datasets change during runtime.
    """

    data = load_dataset(TARGET_FILE)
    return data.get(normalize_key(plant_type), {}) if isinstance(data, Mapping) else {}


def evaluate_nue(nue: Mapping[str, float], plant_type: str, tolerance: float = 0.1) -> Dict[str, Dict[str, Any]]:
    """Return NUE assessment compared to targets.

    Parameters
    ----------
    nue : Mapping[str, float]
        Computed nutrient use efficiency values.
    plant_type : str
        Crop name used to look up targets in :data:`TARGET_FILE`.
    tolerance : float, optional
        Fractional difference allowed before classifying as above or below target.
    """

    targets = _load_targets(plant_type)
    results: Dict[str, Dict[str, Any]] = {}
    for nutrient, value in nue.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        target = float(targets.get(nutrient, 0))
        lower = target * (1 - tolerance)
        upper = target * (1 + tolerance)
        if target > 0:
            if val < lower:
                status = "below target"
            elif val > upper:
                status = "above target"
            else:
                status = "within target"
        else:
            status = "no target"
        results[nutrient] = {"nue": val, "target": target, "status": status}
    return results


def evaluate_plant_nue(plant_id: str, plant_type: str, tolerance: float = 0.1) -> Dict[str, Dict[str, Any]]:
    """Return NUE evaluation for a plant using logged data."""

    info = calculate_nue(plant_id)
    nue_map = info.get("nue", {})
    return evaluate_nue(nue_map, plant_type, tolerance)
