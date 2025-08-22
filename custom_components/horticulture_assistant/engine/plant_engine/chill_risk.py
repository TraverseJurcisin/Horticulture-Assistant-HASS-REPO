"""Forecast chilling injury risk based on upcoming temperatures."""
from __future__ import annotations

from typing import Mapping, Sequence

from .utils import load_dataset, normalize_key, list_dataset_entries

COLD_DATA_FILE = "local/plants/temperature/cold_stress_thresholds.json"
SENSITIVITY_FILE = "local/plants/temperature/chill_sensitivity.json"

_COLD_THRESHOLDS: Mapping[str, float] = load_dataset(COLD_DATA_FILE)
_SENSITIVITY: Mapping[str, Mapping[str, float]] = load_dataset(SENSITIVITY_FILE)

__all__ = [
    "list_supported_plants",
    "get_chill_buffer",
    "forecast_chilling_risk",
]


def list_supported_plants() -> list[str]:
    """Return plant types with chill sensitivity data."""
    return list_dataset_entries(_SENSITIVITY)


def get_chill_buffer(plant_type: str) -> float:
    """Return early warning buffer in °C for ``plant_type``."""
    entry = _SENSITIVITY.get(normalize_key(plant_type)) or _SENSITIVITY.get("default")
    if isinstance(entry, Mapping):
        try:
            return float(entry.get("buffer_c", 0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _cold_threshold(plant_type: str) -> float | None:
    try:
        return float(_COLD_THRESHOLDS.get(normalize_key(plant_type), _COLD_THRESHOLDS.get("default")))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def forecast_chilling_risk(
    plant_type: str,
    ambient_lows_c: Sequence[float],
    root_lows_c: Sequence[float],
    past_events: int = 0,
) -> str:
    """Return ``low``, ``moderate`` or ``high`` chilling injury risk."""
    threshold = _cold_threshold(plant_type)
    if threshold is None:
        return "low"

    buffer = get_chill_buffer(plant_type)
    temps = [float(t) for t in ambient_lows_c if t is not None]
    temps += [float(t) for t in root_lows_c if t is not None]
    if not temps:
        return "low"

    min_temp = min(temps)
    if min_temp <= threshold:
        risk = "high"
    elif min_temp <= threshold + buffer:
        risk = "moderate"
    else:
        risk = "low"

    if past_events > 0 and risk != "high":
        risk = "high" if buffer >= 2 else "moderate"

    return risk
