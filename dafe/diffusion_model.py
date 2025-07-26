"""Wrapper module exposing diffusion helpers from :mod:`plant_engine`."""

from __future__ import annotations

from plant_engine.nutrient_diffusion import (
    calculate_effective_diffusion,
    calculate_diffusion_flux,
    estimate_diffusion_mass,
)

__all__ = [
    "calculate_effective_diffusion",
    "calculate_diffusion_flux",
    "estimate_diffusion_mass",
]
