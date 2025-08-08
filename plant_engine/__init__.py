"""Compatibility wrapper for the relocated `plant_engine` package."""

from __future__ import annotations

import sys
import types
from importlib import import_module
from pathlib import Path

_REAL_NAME = "custom_components.horticulture_assistant.plant_engine"
_REAL_PATH = Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant" / "plant_engine"

# Provide a temporary module with the real package path so that imports like
# ``plant_engine.utils`` resolve while the actual package is being loaded.
_placeholder = types.ModuleType(__name__)
_placeholder.__path__ = [_REAL_PATH.as_posix()]
sys.modules[__name__] = _placeholder

# Import the real implementation and expose it under the top-level name.
_pkg = import_module(_REAL_NAME)
sys.modules[__name__] = _pkg

# Re-export public attributes for direct access.
for name in getattr(_pkg, "__all__", []):
    try:
        globals()[name] = getattr(_pkg, name)
    except AttributeError:
        # Some names are provided dynamically via __getattr__ in the real
        # package; ignore those that are not yet defined at import time.
        pass

__all__ = getattr(_pkg, "__all__", [])
