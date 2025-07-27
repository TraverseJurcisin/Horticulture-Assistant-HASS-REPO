"""Species profile definitions for DAFE.

The module exposes a small registry of plant specific properties used by the
Diffusion Aware Fertigation Engine.  ``get_species_profile`` returns a typed
dataclass so attributes can be accessed with auto-completion while remaining
lightweight for the simple test suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["SpeciesProfile", "get_species_profile"]


@dataclass(frozen=True)
class SpeciesProfile:
    """Container for plant characteristics."""

    root_depth: str
    dryback_tolerance: str
    oxygen_min: float
    ideal_wc_plateau: float
    generative_threshold: float
    ec_low: float
    ec_high: float


_PROFILES = {
    "Cannabis_sativa": {
        "root_depth": "shallow",
        "dryback_tolerance": "medium",
        "oxygen_min": 8,
        "ideal_wc_plateau": 0.42,
        "generative_threshold": 0.035,
        "ec_low": 1.5,
        "ec_high": 2.5,
    }
}


def get_species_profile(species_name: str) -> Optional[SpeciesProfile]:
    """Return a :class:`SpeciesProfile` or ``None`` if ``species_name`` unknown."""

    data = _PROFILES.get(species_name)
    return SpeciesProfile(**data) if data else None
