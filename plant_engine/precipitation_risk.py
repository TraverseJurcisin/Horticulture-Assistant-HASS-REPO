"""Mineral precipitation risk assessment utilities."""
from __future__ import annotations

from typing import Dict, Iterable, Mapping

from .utils import load_dataset, list_dataset_entries, normalize_key

DATA_FILE = "species/species_precipitation_risk.json"

_DATA: Dict[str, Iterable[Dict[str, object]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_precipitation_rules",
    "estimate_precipitation_risk",
]


def list_supported_plants() -> list[str]:
    """Return plant types with precipitation risk definitions."""
    return list_dataset_entries(_DATA)


def get_precipitation_rules(plant_type: str) -> Iterable[Dict[str, object]]:
    """Return precipitation risk rules for ``plant_type``."""
    data = _DATA.get(normalize_key(plant_type))
    return data if isinstance(data, Iterable) else []


def estimate_precipitation_risk(
    plant_type: str,
    dosing_history: Mapping[str, float],
    ph: float,
    ec: float,
) -> Dict[str, Dict[str, object]]:
    """Return precipitation risk levels for ``plant_type``.

    Parameters
    ----------
    plant_type : str
        Crop identifier for dataset lookup.
    dosing_history : Mapping[str, float]
        Recent nutrient application amounts.
    ph : float
        Solution pH.
    ec : float
        Solution EC in mS/cm.
    """

    rules = get_precipitation_rules(plant_type)
    risks: Dict[str, Dict[str, object]] = {}
    for rule in rules:
        nutrients = rule.get("nutrients")
        if not isinstance(nutrients, Iterable):
            continue
        if not all(n in dosing_history for n in nutrients):
            continue
        ph_threshold = rule.get("ph_threshold")
        if ph_threshold is not None and ph <= float(ph_threshold):
            continue
        ec_threshold = rule.get("ec_threshold")
        if ec_threshold is not None and ec < float(ec_threshold):
            continue
        pair = "_".join(nutrients)
        risks[pair] = {
            "level": "high",
            "message": str(rule.get("message", "")),
        }
    return risks
