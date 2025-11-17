"""Simple helpers for working with the tags registry."""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path

__all__ = ["list_tags", "get_plants_with_tag", "search_tags"]

# ``tags.json`` lives alongside the integration package. Using ``parents[3]``
# accidentally walked up to the repository root leaving us to look for a file
# that does not exist.  Resolve the package directory explicitly so lookups
# work regardless of the working directory.
_TAGS_FILE = Path(__file__).resolve().parent.parent / "tags.json"


def _normalise_plants(value: object) -> list[str]:
    """Return a list of plant identifiers derived from ``value``."""

    if value is None:
        return []
    if isinstance(value, str):
        plant = value.strip()
        return [plant] if plant else []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        plants: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                plants.append(text)
        return plants
    text = str(value).strip()
    return [text] if text else []


@cache
def _load_tags() -> dict[str, list[str]]:
    """Return contents of ``tags.json`` as ``{tag: [plant_ids]}``."""
    if not _TAGS_FILE.exists():
        return {}
    with open(_TAGS_FILE, encoding="utf-8") as f:
        try:
            data = json.load(f)
            tags: dict[str, list[str]] = {}
            for key, value in data.items():
                plants = _normalise_plants(value)
                if plants:
                    tags[str(key)] = plants
            return tags
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
