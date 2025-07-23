"""Utility helpers for reading data files used across the plant engine."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping

__all__ = [
    "load_json",
    "save_json",
    "load_dataset",
    "normalize_key",
    "list_dataset_entries",
    "deep_update",
]


def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Write a dictionary to a JSON file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def deep_update(base: Dict[str, Any], other: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``other`` into ``base`` and return ``base``."""

    for key, value in other.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, Mapping)
        ):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


# Default data directory is the repository ``data`` folder. It can be
# overridden using ``HORTICULTURE_DATA_DIR``. An optional overlay directory
# ``HORTICULTURE_OVERLAY_DIR`` can hold user-provided files that merge with
# the defaults. This allows extending or overriding individual datasets
# without copying the entire directory.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OVERLAY_ENV = "HORTICULTURE_OVERLAY_DIR"

def _data_dir() -> Path:
    env = os.getenv("HORTICULTURE_DATA_DIR")
    return Path(env) if env else DEFAULT_DATA_DIR


def _overlay_dir() -> Path | None:
    env = os.getenv(OVERLAY_ENV)
    return Path(env) if env else None


@lru_cache(maxsize=None)
def load_dataset(filename: str) -> Dict[str, Any]:
    """Return dataset ``filename`` merged with any overlay data."""

    base_path = _data_dir() / filename
    data: Dict[str, Any] = {}
    if base_path.exists():
        data = load_json(str(base_path))

    overlay = _overlay_dir()
    if overlay:
        overlay_path = overlay / filename
        if overlay_path.exists():
            extra = load_json(str(overlay_path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra

    return data


def normalize_key(key: str) -> str:
    """Return ``key`` normalized for case-insensitive dataset lookups."""
    return str(key).lower().replace(" ", "_")


def list_dataset_entries(dataset: Mapping[str, Any]) -> list[str]:
    """Return sorted top-level keys from a dataset mapping."""

    return sorted(str(k) for k in dataset.keys())
