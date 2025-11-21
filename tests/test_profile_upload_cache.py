import json
from pathlib import Path

from custom_components.horticulture_assistant.utils.profile_upload_cache import cache_profile_for_upload


class _DummyConfig:
    def __init__(self, base: Path) -> None:
        self._base = base

    def path(self, *parts: str) -> str:
        return str(self._base.joinpath(*parts))


class _DummyHass:
    def __init__(self, base: Path) -> None:
        self.config = _DummyConfig(base)


def test_cache_profile_for_upload_creates_combined_file(tmp_path) -> None:
    plant_dir = tmp_path / "plants" / "basil"
    plant_dir.mkdir(parents=True)

    for name, payload in {
        "general.json": {"name": "Basil"},
        "environment.json": {"light": "full"},
        "nutrition.json": {"n": 10},
        "irrigation.json": {"schedule": "daily"},
        "stages.json": {"seedling": {}},
    }.items():
        (plant_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    hass = _DummyHass(tmp_path)

    cache_profile_for_upload("basil", hass)

    cache_file = tmp_path / "data" / "profile_cache" / "basil.json"
    assert cache_file.exists()

    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cached == {
        "general": {"name": "Basil"},
        "environment": {"light": "full"},
        "nutrition": {"n": 10},
        "irrigation": {"schedule": "daily"},
        "stages": {"seedling": {}},
    }
