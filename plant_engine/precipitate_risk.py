"""Predict risk of mineral precipitation for nutrient blends."""
from __future__ import annotations

from typing import Mapping, Dict

from .utils import load_dataset, list_dataset_entries, normalize_key

DATA_FILE = "precipitation_risk_factors.json"

# Cached dataset
_DATA: Dict[str, Dict[str, Mapping[str, object]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "estimate_precipitate_risk",
]


def list_supported_plants() -> list[str]:
    """Return plant types with precipitation risk data."""
    return list_dataset_entries(_DATA)


def _nutrient_set(levels: Mapping[str, float]) -> set[str]:
    return {normalize_key(n) for n, val in levels.items() if val is not None and val > 0}


def estimate_precipitate_risk(
    plant_type: str,
    nutrient_levels: Mapping[str, float],
    ph: float,
    ec: float | None = None,
    history: Mapping[str, float] | None = None,
) -> Dict[str, str]:
    """Return risk messages triggered by the nutrient solution state."""
    factors = _DATA.get(normalize_key(plant_type), {})
    if not factors:
        return {}

    available = _nutrient_set(nutrient_levels)
    if history:
        available.update(_nutrient_set(history))

    results: Dict[str, str] = {}
    for pair, info in factors.items():
        req = {normalize_key(n) for n in pair.split("_")}
        extra = info.get("nutrients")
        if isinstance(extra, Mapping):
            req.update(normalize_key(n) for n in extra.keys())
        if not req.issubset(available):
            continue
        ph_gt = info.get("ph_gt")
        ph_lt = info.get("ph_lt")
        ec_gt = info.get("ec_gt")
        ec_lt = info.get("ec_lt")
        if ph_gt is not None and ph <= float(ph_gt):
            continue
        if ph_lt is not None and ph >= float(ph_lt):
            continue
        if ec is not None:
            if ec_gt is not None and ec <= float(ec_gt):
                continue
            if ec_lt is not None and ec >= float(ec_lt):
                continue
        results[pair] = str(info.get("message", "precipitation risk"))
    return results
