"""Species profile definitions for the Diffusion-Aware Fertigation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from plant_engine.utils import load_dataset

# Dataset file residing under ``data/`` used to populate known species profiles.
DATA_FILE = "dafe_species_profiles.json"

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


def _profile_data() -> dict:
    """Return cached species profile data from :data:`DATA_FILE`."""

    return load_dataset(DATA_FILE)


@lru_cache(maxsize=None)
def get_species_profile(species_name: str) -> SpeciesProfile | None:
    """Return a :class:`SpeciesProfile` for ``species_name`` if available."""

    data = _profile_data().get(species_name)
    if not data:
        return None
    return SpeciesProfile(species_name, **data)
