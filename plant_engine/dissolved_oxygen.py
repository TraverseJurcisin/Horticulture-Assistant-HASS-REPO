"""Dissolved oxygen management utilities."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "dissolved_oxygen_guidelines.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_oxygen_range",
    "evaluate_dissolved_oxygen",
    "recommend_oxygen_adjustment",
]


def list_supported_plants() -> list[str]:
    """Return plant types with dissolved oxygen guidelines."""
    return list_dataset_entries(_DATA)


def get_oxygen_range(plant_type: str) -> tuple[float, float] | None:
    """Return the recommended (min, max) dissolved oxygen range."""
    entry = _DATA.get(normalize_key(plant_type)) or _DATA.get("default")
    if not isinstance(entry, Mapping):
        return None
    try:
        low = float(entry.get("min"))
        high = float(entry.get("max"))
    except (TypeError, ValueError):
        return None
    return low, high


def evaluate_dissolved_oxygen(do_ppm: float | None, plant_type: str) -> str | None:
    """Return ``"low"`` or ``"high"`` if ``do_ppm`` is outside the recommended range."""
    if do_ppm is None:
        return None
    rng = get_oxygen_range(plant_type)
    if not rng:
        return None
    low, high = rng
    if do_ppm < low:
        return "low"
    if do_ppm > high:
        return "high"
    return None


def recommend_oxygen_adjustment(do_ppm: float | None, plant_type: str) -> str | None:
    """Return ``"aerate"`` if oxygen is low or ``"reduce_aeration"`` if high."""
    level = evaluate_dissolved_oxygen(do_ppm, plant_type)
    if level == "low":
        return "aerate"
    if level == "high":
        return "reduce_aeration"
    return None
