"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module

from . import (environment_tips, hardiness_zone, height_manager, ingredients,
               media_manager, reference_data, utils)
from .crop_advisor import CropAdvice, generate_crop_advice
from .environment_tips import *  # noqa: F401,F403
from .fertigation_optimizer import generate_fertigation_plan
from .growth_rate_manager import estimate_growth, get_daily_growth_rate
from .growth_rate_manager import \
    list_supported_plants as list_growth_rate_plants
from .ingredients import *  # noqa: F401,F403
from .media_manager import *  # noqa: F401,F403
from .nutrient_absorption import apply_absorption_rates, get_absorption_rates
from .nutrient_absorption import list_stages as list_absorption_stages
from .nutrient_conversion import get_conversion_factors, oxide_to_elemental
from .nutrient_planner import (NutrientManagementReport,
                               generate_nutrient_management_report)
from .nutrient_synergy import (apply_synergy_adjustments, get_synergy_factor,
                               list_synergy_pairs)
from .precipitation_risk import estimate_precipitation_risk
from .precipitation_risk import \
    list_supported_plants as list_precipitation_plants
from .reference_data import load_reference_data, refresh_reference_data
from .utils import *  # noqa: F401,F403

__all__ = sorted(
    set(utils.__all__)
    | set(environment_tips.__all__)
    | set(media_manager.__all__)
    | set(ingredients.__all__)
    | set(height_manager.__all__)
    | set(hardiness_zone.__all__)
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
        "generate_fertigation_plan",
        "list_growth_rate_plants",
        "get_daily_growth_rate",
        "estimate_growth",
        "get_conversion_factors",
        "oxide_to_elemental",
        "CropAdvice",
        "generate_crop_advice",
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
