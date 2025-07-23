"""Compatibility wrapper for common JSON helpers.

The original implementation duplicated utilities provided in
:mod:`plant_engine.utils`. This module now simply re-exports
:func:`load_json` and :func:`save_json` to centralise data handling.
"""

from plant_engine.utils import load_json, save_json

__all__ = ["load_json", "save_json"]
