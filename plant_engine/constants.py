"""Central constants used across the plant engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Dict

from .utils import load_dataset, lazy_dataset, normalize_key

_MULTIPLIER_FILE = "stage_multipliers.json"
_DEFAULT_MULTIPLIERS: dict[str, float] = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 1.2,
    "fruiting": 1.1,
}

_multipliers = lazy_dataset(_MULTIPLIER_FILE)

# Path of the dataset providing baseline environment readings
DEFAULT_ENV_FILE = "default_environment.json"
_DEFAULT_ENV_FALLBACK: dict[str, float] = {
    "temp_c": 26,
    "temp_c_max": 30,
    "temp_c_min": 22,
    "rh_pct": 65,
    "par_w_m2": 350,
    "wind_speed_m_s": 1.2,
}


@dataclass(slots=True)
class EnvironmentDefaults:
    """Container for default environmental conditions."""

    temp_c: float
    temp_c_max: float
    temp_c_min: float
    rh_pct: float
    par_w_m2: float
    wind_speed_m_s: float

    def as_dict(self) -> Dict[str, float]:
        """Return the defaults as a regular dictionary."""
        return asdict(self)


def _load_default_env_dict() -> dict[str, float]:
    """Return default environment values from dataset with fallback.

    The dataset may be overridden via ``HORTICULTURE_OVERLAY_DIR``. Invalid
    or missing values gracefully fall back to :data:`_DEFAULT_ENV_FALLBACK`.
    """

    data = load_dataset(DEFAULT_ENV_FILE)
    if not isinstance(data, Mapping):
        return dict(_DEFAULT_ENV_FALLBACK)
    result: dict[str, float] = {}
    for k, v in data.items():
        try:
            result[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return {**_DEFAULT_ENV_FALLBACK, **result}


def load_default_environment() -> EnvironmentDefaults:
    """Return :class:`EnvironmentDefaults` loaded from the dataset."""

    values = _load_default_env_dict()
    return EnvironmentDefaults(**values)


def stage_multipliers() -> dict[str, float]:
    """Return cached stage multiplier mapping."""

    data = _multipliers() or _DEFAULT_MULTIPLIERS
    return {k: float(v) for k, v in data.items()}

def get_stage_multiplier(stage: str) -> float:
    """Return nutrient multiplier for ``stage`` with fallback to ``1.0``."""

    return float(stage_multipliers().get(normalize_key(stage), 1.0))

# Default environment readings applied when a plant profile lacks recent data.
DEFAULT_ENV: dict[str, float] = _load_default_env_dict()
# Typed dataclass version for convenience
DEFAULT_ENV_OBJ: EnvironmentDefaults = load_default_environment()

__all__ = [
    "stage_multipliers",
    "get_stage_multiplier",
    "DEFAULT_ENV",
    "DEFAULT_ENV_OBJ",
    "DEFAULT_ENV_FILE",
]
