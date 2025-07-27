"""Public API for the Diffusion-Aware Fertigation Engine."""

from __future__ import annotations

import importlib

__all__ = [
    "get_species_profile",
    "get_media_profile",
    "calculate_effective_diffusion",
    "calculate_diffusion_flux",
    "estimate_diffusion_mass",
    "get_current_ec",
    "get_current_wc",
    "generate_pulse_schedule",
    "get_stage_targets",
    "calculate_daily_nutrient_mass",
    "calculate_ec_drift",
    "load_config",
    "parse_args",
    "main",
]


_MODULE_MAP = {
    "get_species_profile": "species_profiles",
    "get_media_profile": "media_models",
    "calculate_effective_diffusion": "diffusion_model",
    "calculate_diffusion_flux": "diffusion_model",
    "estimate_diffusion_mass": "diffusion_model",
    "get_current_ec": "ec_tracker",
    "get_current_wc": "wc_monitor",
    "generate_pulse_schedule": "pulse_scheduler",
    "get_stage_targets": "nutrient_planner",
    "calculate_daily_nutrient_mass": "nutrient_planner",
    "calculate_ec_drift": "ec_model",
    "load_config": "utils",
    "parse_args": "main",
    "main": "main",
}


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module 'dafe' has no attribute {name!r}")
    module = importlib.import_module(f".{_MODULE_MAP[name]}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
