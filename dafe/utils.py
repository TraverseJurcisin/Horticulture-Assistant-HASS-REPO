"""Misc utilities for DAFE."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import yaml

__all__ = ["mm_to_cm", "load_config"]


def mm_to_cm(value_mm: float) -> float:
    """Convert millimeters to centimeters."""
    return value_mm / 10.0


CONFIG_FILE = Path(__file__).resolve().with_name("dafe_config.yaml")


@lru_cache(maxsize=None)
def load_config(path: str | Path = CONFIG_FILE) -> dict:
    """Return configuration values from ``dafe_config.yaml``."""

    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
