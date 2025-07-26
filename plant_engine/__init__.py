"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module

from . import utils
from .utils import *  # noqa: F401,F403

__all__ = sorted(set(utils.__all__))


def __getattr__(name: str):
    if name == "nutrient_diffusion":
        module = import_module(".nutrient_diffusion", __name__)
        globals()[name] = module
        __all__.append(name)
        __all__.extend(getattr(module, "__all__", []))
        return module
    raise AttributeError(f"module 'plant_engine' has no attribute {name!r}")
