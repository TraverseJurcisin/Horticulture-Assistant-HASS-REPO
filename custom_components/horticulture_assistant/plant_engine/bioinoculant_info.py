"""Lookup helper for microbial inoculant attributes."""
from __future__ import annotations

from typing import Dict

from .utils import lazy_dataset, normalize_key, list_dataset_entries

DATA_FILE = "bioinoculants/bioinoculant_attributes.json"

_data = lazy_dataset(DATA_FILE)

__all__ = [
    "list_inoculants",
    "get_inoculant_info",
]


def list_inoculants() -> list[str]:
    """Return all inoculant names available in the dataset."""
    return list_dataset_entries(_data())


def get_inoculant_info(name: str) -> Dict[str, str]:
    """Return attribute mapping for ``name``.

    Lookup is case-insensitive and ignores spaces/underscores.
    """
    norm = normalize_key(name)
    for key, value in _data().items():
        if normalize_key(key) == norm:
            return value
    return {}
