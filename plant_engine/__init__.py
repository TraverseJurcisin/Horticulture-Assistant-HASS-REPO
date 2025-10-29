"""Compatibility shim exposing the vendored ``plant_engine`` package."""

from __future__ import annotations

import importlib
import sys
from typing import Any

_TARGET_PACKAGE = "custom_components.horticulture_assistant.engine.plant_engine"

_target = importlib.import_module(_TARGET_PACKAGE)

__all__ = list(getattr(_target, "__all__", ()))
__path__ = list(getattr(_target, "__path__", []))  # type: ignore[attr-defined]


def _ensure_module_aliases() -> None:
    prefix = f"{_TARGET_PACKAGE}."
    for name, module in list(sys.modules.items()):
        if name.startswith(prefix):
            alias = name.replace(prefix, "plant_engine.", 1)
            sys.modules.setdefault(alias, module)


def __getattr__(name: str) -> Any:
    _ensure_module_aliases()
    value = getattr(_target, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()) | set(dir(_target)))


_ensure_module_aliases()
