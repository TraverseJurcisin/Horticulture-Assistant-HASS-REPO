"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module

from . import utils, environment_tips, media_manager, ingredients, reference_data
from . import height_manager
from .reference_data import load_reference_data, refresh_reference_data
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

__all__ = sorted(
    set(utils.__all__)
    | set(environment_tips.__all__)
    | set(media_manager.__all__)
    | set(ingredients.__all__)
    | set(height_manager.__all__)
    | {"load_reference_data", "refresh_reference_data"}
    | {
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


def __getattr__(name: str):
    if name == "nutrient_diffusion":
        module = import_module(".nutrient_diffusion", __name__)
        globals()[name] = module
        __all__.append(name)
        __all__.extend(getattr(module, "__all__", []))
        return module
    if name == "phenology":
        module = import_module(".phenology", __name__)
        globals()[name] = module
        __all__.append(name)
        __all__.extend(getattr(module, "__all__", []))
        return module
    if name == "thermal_time":
        module = import_module(".thermal_time", __name__)
        globals()[name] = module
        __all__.append(name)
        __all__.extend(getattr(module, "__all__", []))
        return module
    raise AttributeError(f"module 'plant_engine' has no attribute {name!r}")
