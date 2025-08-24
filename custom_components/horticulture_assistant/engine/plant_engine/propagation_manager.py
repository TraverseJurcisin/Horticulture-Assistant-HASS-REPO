"""Utilities for accessing plant propagation guidelines."""

from __future__ import annotations

from collections.abc import Mapping

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "propagation/propagation_guidelines.json"

_DATA: dict[str, dict[str, dict[str, object]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "list_propagation_methods",
    "get_propagation_guidelines",
    "propagation_success_score",
]


def list_supported_plants() -> list[str]:
    """Return plant types with propagation guidelines."""
    return list_dataset_entries(_DATA)


def list_propagation_methods(plant_type: str) -> list[str]:
    """Return supported propagation methods for ``plant_type``."""
    plant = _DATA.get(normalize_key(plant_type), {})
    return sorted(str(m) for m in plant.keys())


def get_propagation_guidelines(plant_type: str, method: str) -> dict[str, object]:
    """Return guideline mapping for ``plant_type`` and ``method``."""
    plant = _DATA.get(normalize_key(plant_type), {})
    return plant.get(normalize_key(method), {})


def propagation_success_score(
    environment: Mapping[str, float], plant_type: str, method: str
) -> float:
    """Return 0-100 score estimating propagation success probability."""
    guide = get_propagation_guidelines(plant_type, method)
    if not guide:
        return 0.0

    total = 0.0
    count = 0
    for key in ("temperature_c", "humidity_pct"):
        target = guide.get(key)
        if not isinstance(target, list | tuple) or len(target) != 2:
            continue
        try:
            value = float(environment.get(key))
        except (TypeError, ValueError):
            continue
        low, high = float(target[0]), float(target[1])
        span = high - low if high > low else 1.0
        if value < low:
            diff = low - value
            score = max(0.0, 1 - diff / span)
        elif value > high:
            diff = value - high
            score = max(0.0, 1 - diff / span)
        else:
            score = 1.0
        total += score
        count += 1

    if count == 0:
        return 0.0
    return round((total / count) * 100, 1)
