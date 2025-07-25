"""Simple helpers for working with the tags registry."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

__all__ = ["list_tags", "get_plants_with_tag", "search_tags"]

_TAGS_FILE = Path(__file__).resolve().parents[3] / "tags.json"


@lru_cache(maxsize=None)
def _load_tags() -> Dict[str, List[str]]:
    """Return contents of ``tags.json`` as ``{tag: [plant_ids]}``."""
    if not _TAGS_FILE.exists():
        return {}
    with open(_TAGS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return {str(k): list(v) for k, v in data.items()}
        except Exception:
            return {}


def list_tags() -> List[str]:
    """Return all available tag names sorted alphabetically."""
    return sorted(_load_tags().keys())


def get_plants_with_tag(tag: str) -> List[str]:
    """Return plant IDs associated with ``tag``."""
    return _load_tags().get(str(tag), [])


def search_tags(term: str) -> Dict[str, List[str]]:
    """Return tags containing ``term`` (case-insensitive)."""
    if not term:
        return {}
    term = term.lower()
    matches: Dict[str, List[str]] = {}
    for tag, plants in _load_tags().items():
        if term in tag.lower():
            matches[tag] = plants
    return matches
