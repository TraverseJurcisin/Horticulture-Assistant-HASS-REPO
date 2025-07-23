"""Helpers for discovering and describing bundled datasets."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATALOG_FILE = DATA_DIR / "dataset_catalog.json"

__all__ = ["list_datasets", "get_dataset_description"]


def list_datasets() -> List[str]:
    """Return the names of available JSON datasets."""
    return sorted(
        p.name for p in DATA_DIR.glob("*.json") if p.name != CATALOG_FILE.name
    )


@lru_cache(maxsize=None)
def _load_catalog() -> Dict[str, str]:
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    return {}


def get_dataset_description(name: str) -> str | None:
    """Return the human readable description for ``name`` if known."""
    return _load_catalog().get(name)
