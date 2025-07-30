"""Growing media guidelines and utilities."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "media/media_properties.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_media",
    "get_media_properties",
]


def list_supported_media() -> list[str]:
    """Return available growing media types."""
    return list_dataset_entries(_DATA)


def get_media_properties(media_type: str) -> Dict[str, float]:
    """Return property mapping for ``media_type``."""
    return {
        k: float(v)
        for k, v in _DATA.get(normalize_key(media_type), {}).items()
        if isinstance(v, (int, float))
    }
