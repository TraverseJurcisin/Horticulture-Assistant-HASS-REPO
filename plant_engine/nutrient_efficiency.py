"""Helpers for analyzing nutrient use efficiency (NUE)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

# Default storage locations can be overridden with environment variables. This
# makes the module more flexible for testing and deployment scenarios where the
# repository's ``data`` directory is not writable.

NUTRIENT_DIR = Path(os.getenv("HORTICULTURE_NUTRIENT_DIR", "data/nutrients_applied"))
YIELD_DIR = Path(os.getenv("HORTICULTURE_YIELD_DIR", "data/yield"))


@dataclass(frozen=True)
class NUEReport:
    """Result container for :func:`calculate_nue`."""

    plant_id: str
    total_yield_g: float
    nue: Dict[str, float | None]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = ["calculate_nue", "NUEReport"]

def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def calculate_nue(plant_id: str) -> Dict[str, Any]:
    """Return nutrient use efficiency values for ``plant_id``."""

    nutrients_path = NUTRIENT_DIR / f"{plant_id}.json"
    if not nutrients_path.exists():
        raise FileNotFoundError(f"No nutrient record found for {plant_id}")

    nutrient_log = _load_json(nutrients_path)
    total_applied_mg: Dict[str, float] = {}
    for entry in nutrient_log.get("records", []):
        for nutrient, value in entry.get("nutrients_mg", {}).items():
            total_applied_mg[nutrient] = total_applied_mg.get(nutrient, 0.0) + float(value)

    yield_path = YIELD_DIR / f"{plant_id}.json"
    if not yield_path.exists():
        raise FileNotFoundError(f"No yield record found for {plant_id}")

    yield_data = _load_json(yield_path)
    total_yield_g = sum(
        float(rec.get("yield_grams", 0.0)) for rec in yield_data.get("harvests", [])
    )

    nue: Dict[str, float | None] = {}
    for nutrient, mg in total_applied_mg.items():
        g_applied = mg / 1000
        nue[nutrient] = round(total_yield_g / g_applied, 2) if g_applied else None

    report = NUEReport(
        plant_id=str(plant_id),
        total_yield_g=round(total_yield_g, 2),
        nue=nue,
    )
    return report.as_dict()
