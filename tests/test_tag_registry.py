"""Tests for tag registry helpers."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.horticulture_assistant.utils import tag_registry


def _write_tags(tmp_path: Path, data: dict[str, list[str]]) -> Path:
    tag_file = tmp_path / "tags.json"
    tag_file.write_text(json.dumps(data), encoding="utf-8")
    return tag_file


def test_get_plants_with_tag_returns_copy(tmp_path, monkeypatch) -> None:
    """Mutating results from ``get_plants_with_tag`` should not affect cache."""

    tag_file = _write_tags(tmp_path, {"herb": ["basil", "mint"]})
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", tag_file, raising=False)
    tag_registry._load_tags.cache_clear()

    plants = tag_registry.get_plants_with_tag("herb")
    plants.append("oregano")

    assert tag_registry.get_plants_with_tag("herb") == ["basil", "mint"]
    tag_registry._load_tags.cache_clear()


def test_search_tags_returns_copies(tmp_path, monkeypatch) -> None:
    """Mutating search results should not alter cached tag data."""

    tag_file = _write_tags(tmp_path, {"herb": ["basil"], "fruit": ["tomato"]})
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", tag_file, raising=False)
    tag_registry._load_tags.cache_clear()

    matches = tag_registry.search_tags("her")
    matches["herb"].append("oregano")

    assert tag_registry.search_tags("her") == {"herb": ["basil"]}
    tag_registry._load_tags.cache_clear()
