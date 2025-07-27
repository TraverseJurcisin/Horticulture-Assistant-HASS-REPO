"""Species profile definitions for the Diffusion-Aware Fertigation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

__all__ = ["SpeciesProfile", "get_species_profile"]


@dataclass(frozen=True, slots=True)
class SpeciesProfile:
    """Container object describing plant characteristics."""

    name: str
    root_depth: str
    dryback_tolerance: str
    oxygen_min: float
    ideal_wc_plateau: float
    generative_threshold: float
    ec_low: float
    ec_high: float


@lru_cache(maxsize=None)
def get_species_profile(species_name: str) -> SpeciesProfile | None:
    """Return a :class:`SpeciesProfile` or ``None`` if ``species_name`` unknown."""

    data = {
        "Cannabis_sativa": {
            "root_depth": "shallow",
            "dryback_tolerance": "medium",
            "oxygen_min": 8.0,
            "ideal_wc_plateau": 0.42,
            "generative_threshold": 0.035,
            "ec_low": 1.5,
            "ec_high": 2.5,
        }
    }.get(species_name)

    if not data:
        return None

    return SpeciesProfile(species_name, **data)
