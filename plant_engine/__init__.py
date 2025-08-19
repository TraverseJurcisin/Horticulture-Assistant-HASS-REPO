"""Compatibility wrapper for the relocated ``plant_engine`` package."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(
    "custom_components.horticulture_assistant.plant_engine"
)
