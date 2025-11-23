"""Tests for caching behaviour in :mod:`bio_profile_loader`."""

from __future__ import annotations

import json
from pathlib import Path

from ..utils import bio_profile_loader as loader


def _write_profile(path: Path, name: str = "Demo") -> None:
    payload = {"general": {"name": name}}
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_profile_from_path_returns_isolated_results(tmp_path) -> None:
    """Each call should return a new mapping, even when cached."""

    profile_path = tmp_path / "demo.json"
    _write_profile(profile_path)

    loader._load_profile_from_path_cached.cache_clear()

    first = loader.load_profile_from_path(profile_path)
    second = loader.load_profile_from_path(profile_path)

    assert first is not second
    first["general"]["name"] = "Mutated"
    assert second["general"]["name"] == "Demo"

    third = loader.load_profile_from_path(profile_path)
    assert third["general"]["name"] == "Demo"


def test_load_profile_by_id_returns_isolated_results(tmp_path) -> None:
    """Cached lookups by id should also return copies of the data."""

    base_dir = tmp_path / "profiles"
    base_dir.mkdir()
    profile_path = base_dir / "demo.json"
    _write_profile(profile_path)

    loader._load_profile_by_id_cached.cache_clear()
    loader._load_profile_from_path_cached.cache_clear()

    first = loader.load_profile_by_id("demo", base_dir)
    second = loader.load_profile_by_id("demo", base_dir)

    assert first is not second
    first["general"]["name"] = "Updated"
    assert second["general"]["name"] == "Demo"

    third = loader.load_profile_by_id("demo", base_dir)
    assert third["general"]["name"] == "Demo"
