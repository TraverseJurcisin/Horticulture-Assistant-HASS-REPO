"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module

from . import utils, environment_tips, media_manager, ingredients
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

__all__ = sorted(
    set(utils.__all__)
    | set(environment_tips.__all__)
    | set(media_manager.__all__)
    | set(ingredients.__all__)
    | {
        "NutrientManagementReport",
        "generate_nutrient_management_report",
        "list_synergy_pairs",
        "get_synergy_factor",
        "apply_synergy_adjustments",
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
