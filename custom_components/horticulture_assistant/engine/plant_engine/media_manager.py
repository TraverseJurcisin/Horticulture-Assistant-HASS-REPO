"""Growing media guidelines and utilities."""

from __future__ import annotations

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "media/media_properties.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_media",
    "get_media_properties",
]


def list_supported_media() -> list[str]:
    """Return available growing media types."""
    return list_dataset_entries(_DATA)


def get_media_properties(media_type: str) -> dict[str, float]:
    """Return property mapping for ``media_type``."""
    return {
        k: float(v)
        for k, v in _DATA.get(normalize_key(media_type), {}).items()
        if isinstance(v, int | float)
    }
