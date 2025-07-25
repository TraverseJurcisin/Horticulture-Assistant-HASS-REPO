"""Convenient access to plant engine functionality."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from . import utils
from .utils import *  # noqa: F401,F403

_ALL = set(utils.__all__)

_PACKAGE_PATH = Path(__file__).resolve().parent
for _, mod_name, is_pkg in iter_modules([str(_PACKAGE_PATH)]):
    if is_pkg or mod_name in {"__init__", "utils"}:
        continue
    module = import_module(f".{mod_name}", __name__)
    globals()[mod_name] = module
    _ALL.add(mod_name)
    _ALL.update(getattr(module, "__all__", []))

__all__ = sorted(_ALL)
