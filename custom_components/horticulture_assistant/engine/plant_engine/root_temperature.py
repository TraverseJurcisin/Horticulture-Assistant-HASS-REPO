"""Root zone temperature impact on nutrient uptake."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping, Sequence
from functools import cache

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "temperature/root_temperature_uptake.json"
OPTIMA_FILE = "local/plants/temperature/root_temperature_optima.json"

_DATA = load_dataset(DATA_FILE)
_OPTIMA = load_dataset(OPTIMA_FILE)
_TEMPS: Sequence[float] = [float(t) for t in _DATA.get("temperature_c", [])]
_FACTORS: Sequence[float] = [float(f) for f in _DATA.get("factor", [])]
_DEFAULT_OPTIMUM = next((t for t, f in zip(_TEMPS, _FACTORS, strict=False) if f == 1.0), 21.0)

__all__ = [
    "list_supported_plants",
    "get_optimal_root_temperature",
    "get_uptake_factor",
    "adjust_uptake",
    "clear_cache",
]


def list_supported_plants() -> list[str]:
    """Return plant types with defined optimal root temperatures."""

    return list_dataset_entries(_OPTIMA)


def get_optimal_root_temperature(plant_type: str) -> float | None:
    """Return optimal root zone temperature for ``plant_type`` when known."""

    value = _OPTIMA.get(normalize_key(plant_type))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - dataset corruption
        return None


@cache
def get_uptake_factor(temp_c: float, plant_type: str | None = None) -> float:
    """Return uptake efficiency factor for ``temp_c`` in Celsius.

    When ``plant_type`` is provided and an optimum temperature is defined in
    :data:`root_temperature_optima.json`, the lookup adjusts the curve so that
    the optimum factor of ``1.0`` occurs at the crop specific temperature.

    Results are cached to speed up repeated calls with the same parameters.
    """
    if not _TEMPS or len(_TEMPS) != len(_FACTORS):
        return 1.0

    if plant_type:
        opt = _OPTIMA.get(plant_type.lower())
        if isinstance(opt, int | float):
            temp_c = temp_c + (_DEFAULT_OPTIMUM - float(opt))

    idx = bisect_left(_TEMPS, temp_c)
    if idx <= 0:
        return float(_FACTORS[0])
    if idx >= len(_TEMPS):
        return float(_FACTORS[-1])
    lo_t, hi_t = _TEMPS[idx - 1], _TEMPS[idx]
    lo_f, hi_f = _FACTORS[idx - 1], _FACTORS[idx]
    fraction = (temp_c - lo_t) / (hi_t - lo_t)
    return round(lo_f + fraction * (hi_f - lo_f), 3)


def adjust_uptake(
    uptake: Mapping[str, float], temp_c: float, plant_type: str | None = None
) -> dict[str, float]:
    """Return ``uptake`` scaled by the temperature factor."""
    factor = get_uptake_factor(temp_c, plant_type)
    return {nutrient: round(value * factor, 2) for nutrient, value in uptake.items()}


def clear_cache() -> None:
    """Clear cached results for temperature factor lookups."""
    get_uptake_factor.cache_clear()
