"""Tests for the profile generator scaffolding helper."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.horticulture_assistant.utils.profile_generator import generate_profile


class _DummyConfig:
    def __init__(self, base: Path) -> None:
        self._base = base

    def path(self, *parts: str) -> str:
        return str(self._base.joinpath(*parts))


class _DummyHass:
    def __init__(self, base: Path) -> None:
        self.config = _DummyConfig(base)


def test_generate_profile_creates_template_files(tmp_path) -> None:
    hass = _DummyHass(tmp_path)
    metadata = {"display_name": "Test Plant", "plant_type": "Herb"}

    plant_id = generate_profile(metadata, hass=hass)

    assert plant_id == "test_plant"

    plant_dir = tmp_path / "plants" / plant_id
    assert plant_dir.is_dir()
    general = json.loads((plant_dir / "general.json").read_text(encoding="utf-8"))
    assert general["display_name"] == "Test Plant"

    cache_file = tmp_path / "data" / "profile_cache" / f"{plant_id}.json"
    assert cache_file.exists()


def test_generate_profile_accepts_iterable_tags(tmp_path) -> None:
    hass = _DummyHass(tmp_path)
    metadata = {
        "display_name": "Berry Plant",
        "tags": ("Needs Sun", "berries"),
        "location": "Greenhouse",
    }

    plant_id = generate_profile(metadata, hass=hass)

    plant_dir = tmp_path / "plants" / plant_id
    general = json.loads((plant_dir / "general.json").read_text(encoding="utf-8"))

    assert general["tags"]
    assert "needs_sun" in general["tags"]
    # Location is appended as tag when not already present.
    assert "greenhouse" in general["tags"]
