"""Stage-based nutrient adjustment factors."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_stage_factors.json"

_FACTORS: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["get_stage_factor", "list_stages"]


def list_stages() -> list[str]:
    """Return stages with defined nutrient factors."""
    return sorted(_FACTORS.keys())


@lru_cache(maxsize=None)
def get_stage_factor(stage: str) -> float:
    """Return nutrient multiplier for ``stage``.

    If no factor is defined a value of ``1.0`` is returned.
    """
    return float(_FACTORS.get(normalize_key(stage), 1.0))
