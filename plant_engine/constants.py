"""Central constants used across the plant engine."""

from __future__ import annotations

from .utils import lazy_dataset, normalize_key

_MULTIPLIER_FILE = "stage_multipliers.json"
_DEFAULT_MULTIPLIERS: dict[str, float] = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 1.2,
    "fruiting": 1.1,
}

_multipliers = lazy_dataset(_MULTIPLIER_FILE)


def stage_multipliers() -> dict[str, float]:
    """Return cached stage multiplier mapping."""

    data = _multipliers() or _DEFAULT_MULTIPLIERS
    return {k: float(v) for k, v in data.items()}

def get_stage_multiplier(stage: str) -> float:
    """Return nutrient multiplier for ``stage`` with fallback to ``1.0``."""

    return float(stage_multipliers().get(normalize_key(stage), 1.0))

# Default environment readings applied when a plant profile lacks recent data.
DEFAULT_ENV: dict[str, float] = {
    "temp_c": 26,
    "temp_c_max": 30,
    "temp_c_min": 22,
    "rh_pct": 65,
    "par_w_m2": 350,
    "wind_speed_m_s": 1.2,
}

__all__ = ["stage_multipliers", "get_stage_multiplier", "DEFAULT_ENV"]
