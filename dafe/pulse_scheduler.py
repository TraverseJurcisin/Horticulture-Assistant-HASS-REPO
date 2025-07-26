"""Irrigation pulse scheduler for DAFE."""

from __future__ import annotations

from datetime import datetime, timedelta

__all__ = ["generate_pulse_schedule"]

from .diffusion_model import estimate_diffusion_mass


def generate_pulse_schedule(
    wc: float,
    ec: float,
    D_eff: float,
    species_profile: dict,
    media_profile: dict,
    *,
    nutrient_params: dict | None = None,
    start_hour: int = 10,
    hours: int = 6,
) -> list[dict]:
    """Return a basic irrigation schedule.

    Parameters
    ----------
    wc, ec : float
        Current water content and EC values.
    D_eff : float
        Effective diffusion coefficient.
    species_profile, media_profile : dict
        Definitions of plant and substrate characteristics.
    nutrient_params : dict | None, optional
        Additional parameters for :func:`estimate_diffusion_mass`.
    start_hour : int, optional
        Hour offset from ``now`` for the first pulse. Default is 10.
    hours : int, optional
        Number of hourly pulses to schedule. Default is 6.
    """
    if not 0 <= start_hour < 24:
        raise ValueError("start_hour must be between 0 and 23")
    if hours <= 0:
        raise ValueError("hours must be positive")

    schedule = []
    current_time = datetime.now().replace(minute=0, second=0, microsecond=0)

    nutrient_params = nutrient_params or {}
    D_base = nutrient_params.get("D_base", 1e-5)
    conc_high = nutrient_params.get("conc_high", 100.0)
    conc_low = nutrient_params.get("conc_low", 50.0)
    distance_cm = nutrient_params.get("distance_cm", 1.0)
    area_cm2 = nutrient_params.get("area_cm2", 10.0)
    duration_s = nutrient_params.get("duration_s", 3600.0)

    for offset in range(hours):
        hour = start_hour + offset
        if wc < species_profile["ideal_wc_plateau"]:
            pulse_volume = int(30 + D_eff * 100000)
            ec_low = species_profile.get("ec_low", 1.5)
            ec_high = species_profile.get("ec_high", 2.5)
            if ec > ec_high:
                pulse_volume = int(pulse_volume * 0.8)
            elif ec < ec_low:
                pulse_volume = int(pulse_volume * 1.2)
            mass_mg = estimate_diffusion_mass(
                D_base,
                wc,
                media_profile["porosity"],
                media_profile["tortuosity"],
                conc_high,
                conc_low,
                distance_cm,
                area_cm2,
                duration_s,
            )
            schedule.append(
                {
                    "time": (current_time + timedelta(hours=hour)).strftime(
                        "%H:%M"
                    ),
                    "volume": pulse_volume,
                    "mass_mg": mass_mg,
                }
            )

    return schedule
