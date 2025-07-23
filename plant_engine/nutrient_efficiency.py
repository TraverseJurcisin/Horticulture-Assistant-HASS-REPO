"""Calculate nutrient use efficiency from application and yield logs."""

import os
import json
from dataclasses import dataclass, asdict
from typing import Dict

# Default storage locations can be overridden with environment variables. This
# makes the module more flexible for testing and deployment scenarios where the
# repository's ``data`` directory is not writable.
NUTRIENT_DIR = os.getenv("HORTICULTURE_NUTRIENT_DIR", "data/nutrients_applied")
YIELD_DIR = os.getenv("HORTICULTURE_YIELD_DIR", "data/yield")

@dataclass
class NUEReport:
    """Nutrient use efficiency summary."""

    plant_id: str
    total_yield_g: float
    nue: Dict[str, float | None]

    def as_dict(self) -> Dict[str, object]:
        """Return the report as a plain dictionary."""
        return asdict(self)


def calculate_nue(plant_id: str) -> NUEReport:
    """Return nutrient use efficiency report for ``plant_id``."""

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

    return NUEReport(
        plant_id=plant_id,
        total_yield_g=total_yield_g,
        nue=nue,
    )
