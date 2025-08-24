"""Nutrient solution temperature guidelines and helpers."""

from __future__ import annotations

from collections.abc import Mapping

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "temperature/solution_temperature_guidelines.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_temperature_range",
    "evaluate_solution_temperature",
    "recommend_temperature_adjustment",
]


def list_supported_plants() -> list[str]:
    """Return plant types with solution temperature guidelines."""
    return list_dataset_entries(_DATA)


def get_temperature_range(plant_type: str) -> tuple[float, float] | None:
    """Return (min, max) solution temperature range for ``plant_type``."""
    entry = _DATA.get(normalize_key(plant_type)) or _DATA.get("default")
    if not isinstance(entry, Mapping):
        return None
    try:
        low = float(entry.get("min"))
        high = float(entry.get("max"))
    except (TypeError, ValueError):
        return None
    return low, high


def evaluate_solution_temperature(temp_c: float | None, plant_type: str) -> str | None:
    """Return ``"low"`` or ``"high"`` if temperature is outside the range."""
    if temp_c is None:
        return None
    rng = get_temperature_range(plant_type)
    if not rng:
        return None
    low, high = rng
    if temp_c < low:
        return "low"
    if temp_c > high:
        return "high"
    return None


def recommend_temperature_adjustment(temp_c: float | None, plant_type: str) -> str | None:
    """Return a suggestion to heat or cool the solution if needed."""
    level = evaluate_solution_temperature(temp_c, plant_type)
    if level == "low":
        return "heat"
    if level == "high":
        return "cool"
    return None
