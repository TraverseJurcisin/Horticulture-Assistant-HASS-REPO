"""Nutrient diffusion utilities for porous media."""
from __future__ import annotations

__all__ = [
    "calculate_effective_diffusion",
    "calculate_diffusion_flux",
    "estimate_diffusion_mass",
]


def calculate_effective_diffusion(
    D_base: float,
    vwc: float,
    porosity: float,
    tortuosity: float,
) -> float:
    """Return effective diffusion coefficient ``D_eff`` in cm^2/s.

    Parameters
    ----------
    D_base : float
        Diffusion coefficient of the solute in free water (cm^2/s).
    vwc : float
        Volumetric water content of the substrate (0-1).
    porosity : float
        Total pore volume fraction of the substrate (0-1).
    tortuosity : float
        Tortuosity factor for the medium.
    """
    if D_base <= 0 or porosity <= 0 or tortuosity <= 0:
        raise ValueError("D_base, porosity and tortuosity must be positive")
    if not 0 <= vwc <= 1:
        raise ValueError("vwc must be between 0 and 1")

    return D_base * (vwc / porosity) ** tortuosity


def calculate_diffusion_flux(
    D_base: float,
    vwc: float,
    porosity: float,
    tortuosity: float,
    conc_high: float,
    conc_low: float,
    distance_cm: float,
) -> float:
    """Return nutrient flux in mg/(cm^2*s) using Fick's Law.

    Concentration values are in mg/cm^3 and ``distance_cm`` is the
    separation between the two concentrations.
    """
    if distance_cm <= 0:
        raise ValueError("distance_cm must be positive")

    D_eff = calculate_effective_diffusion(D_base, vwc, porosity, tortuosity)
    gradient = (conc_high - conc_low) / distance_cm
    return -D_eff * gradient


def estimate_diffusion_mass(
    D_base: float,
    vwc: float,
    porosity: float,
    tortuosity: float,
    conc_high: float,
    conc_low: float,
    distance_cm: float,
    area_cm2: float,
    duration_s: float,
) -> float:
    """Return nutrient mass diffusing across ``area_cm2`` in milligrams."""
    if area_cm2 <= 0 or duration_s <= 0:
        raise ValueError("area_cm2 and duration_s must be positive")

    flux = calculate_diffusion_flux(
        D_base, vwc, porosity, tortuosity, conc_high, conc_low, distance_cm
    )
    mass = abs(flux) * area_cm2 * duration_s
    return mass

