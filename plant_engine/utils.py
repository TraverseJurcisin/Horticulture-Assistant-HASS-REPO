"""Utility helpers for reading data files used across the plant engine."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

__all__ = ["load_json", "save_json", "load_dataset"]


def load_json(path: str) -> Dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Write a dictionary to a JSON file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=None)
def load_dataset(filename: str) -> Dict[str, Any]:
    """Load a JSON dataset from the repository ``data`` directory with caching."""
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    return load_json(str(path))
