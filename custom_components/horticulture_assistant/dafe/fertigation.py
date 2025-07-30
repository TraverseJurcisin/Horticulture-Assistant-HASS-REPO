"""Convenience wrappers for fertigation utilities."""

from __future__ import annotations

from typing import Mapping, Dict

from plant_engine.fertigation import recommend_fertigation_schedule as _recommend

__all__ = ["recommend_fertigation_schedule"]


def recommend_fertigation_schedule(
    plant_type: str,
    stage: str,
    volume_l: float,
    purity: Mapping[str, float] | None = None,
    *,
    product: str | None = None,
) -> Dict[str, float]:
    """Return fertilizer grams for a nutrient solution.

    This is a thin wrapper around
    :func:`plant_engine.fertigation.recommend_fertigation_schedule`
    allowing DAFE to expose nutrient planning features without
    requiring callers to import :mod:`plant_engine` directly.
    """

    return _recommend(plant_type, stage, volume_l, purity, product=product)
