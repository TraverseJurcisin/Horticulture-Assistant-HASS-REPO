"""Simple helpers for working with the tags registry."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

__all__ = ["list_tags", "get_plants_with_tag", "search_tags"]

_TAGS_FILE = Path(__file__).resolve().parents[1] / "tags.json"


@cache
def _load_tags() -> dict[str, list[str]]:
    """Return contents of ``tags.json`` as ``{tag: [plant_ids]}``."""
    if not _TAGS_FILE.exists():
        return {}
    with open(_TAGS_FILE, encoding="utf-8") as f:
        try:
            data = json.load(f)
            return {str(k): list(v) for k, v in data.items()}
        except Exception:
            return {}


def list_tags() -> list[str]:
    """Return all available tag names sorted alphabetically."""
    return sorted(_load_tags().keys())


def get_plants_with_tag(tag: str) -> list[str]:
    """Return plant IDs associated with ``tag`` as a new list copy."""

    plants = _load_tags().get(str(tag))
    if plants is None:
        return []
    return list(plants)


def search_tags(term: str) -> dict[str, list[str]]:
    """Return tags containing ``term`` (case-insensitive)."""

    if not term:
        return {}

    term = term.lower()
    matches: dict[str, list[str]] = {}
    for tag, plants in _load_tags().items():
        if term in tag.lower():
            matches[tag] = list(plants)
    return matches
