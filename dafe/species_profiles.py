"""Mock species profiles for DAFE."""

from __future__ import annotations

__all__ = ["get_species_profile"]


def get_species_profile(species_name: str) -> dict | None:
    """Return a species profile dictionary or ``None`` if unknown."""
    profiles = {
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
    return profiles.get(species_name)
