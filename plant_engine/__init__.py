"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module

from . import utils, environment_tips, media_manager, ingredients, reference_data
from .reference_data import load_reference_data
from .utils import *  # noqa: F401,F403
from .environment_tips import *  # noqa: F401,F403
from .media_manager import *  # noqa: F401,F403
from .ingredients import *  # noqa: F401,F403
from .nutrient_planner import (
    NutrientManagementReport,
    generate_nutrient_management_report,
)
from .nutrient_synergy import (
    list_synergy_pairs,
    get_synergy_factor,
    apply_synergy_adjustments,
)
from .nutrient_absorption import (
    list_stages as list_absorption_stages,
    get_absorption_rates,
    apply_absorption_rates,
)
from .precipitation_risk import (
    list_supported_plants as list_precipitation_plants,
    estimate_precipitation_risk,
)

_MODULE_ALL = (
    utils.__all__
    + environment_tips.__all__
    + media_manager.__all__
    + ingredients.__all__
)

__all__ = sorted(
    set(_MODULE_ALL)
    | {
        "load_reference_data",
        "NutrientManagementReport",
        "generate_nutrient_management_report",
        "list_synergy_pairs",
        "get_synergy_factor",
        "apply_synergy_adjustments",
        "list_absorption_stages",
        "get_absorption_rates",
        "apply_absorption_rates",
        "list_precipitation_plants",
        "estimate_precipitation_risk",
    }
)


_LAZY_MODULES = {
    "nutrient_diffusion",
    "phenology",
    "thermal_time",
}


def __getattr__(name: str):
    if name in _LAZY_MODULES:
        module = import_module(f".{name}", __name__)
        globals()[name] = module
        __all__.append(name)
        __all__.extend(getattr(module, "__all__", []))
        return module
    raise AttributeError(f"module 'plant_engine' has no attribute {name!r}")
