"""Species-linked heat memory utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "heat_memory_profiles.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "apply_heat_event",
    "HeatMemoryIndex",
]


@dataclass(slots=True)
class HeatMemoryIndex:
    """Result describing heat memory adjustments for a plant."""

    plant_id: str
    lag_days: int
    ec_reduction_pct: float
    foliar_ca_days: int

    def as_dict(self) -> Dict[str, float | str]:
        """Return index data as a plain dictionary."""
        return {
            "plant_id": self.plant_id,
            "lag_days": self.lag_days,
            "ec_reduction_pct": self.ec_reduction_pct,
            "foliar_ca_days": self.foliar_ca_days,
        }


def list_supported_plants() -> list[str]:
    """Return plant types with heat memory profiles."""

    return list_dataset_entries(_DATA)


def _get_profile(plant_type: str) -> Dict[str, float]:
    plant = _DATA.get(normalize_key(plant_type))
    if plant is None:
        plant = _DATA.get("default", {})
    return plant if isinstance(plant, dict) else {}


def apply_heat_event(
    plant_id: str,
    plant_type: str,
    days_above_threshold: int,
) -> HeatMemoryIndex:
    """Return heat memory index adjustments for a plant heat event."""

    profile = _get_profile(plant_type)
    lag_per_day = float(profile.get("lag_per_day", 0))
    ec_pct = float(profile.get("ec_reduction_pct", 0))
    ca_days = int(profile.get("foliar_ca_days", 0))
    lag_days = max(0, int(round(lag_per_day * days_above_threshold)))
    return HeatMemoryIndex(
        plant_id=plant_id,
        lag_days=lag_days,
        ec_reduction_pct=ec_pct,
        foliar_ca_days=ca_days,
    )
