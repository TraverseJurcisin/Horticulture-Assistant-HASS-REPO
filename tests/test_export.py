import json
from pathlib import Path

import pytest

from custom_components.horticulture_assistant.profile.export import (
    async_export_profile,
    async_export_profiles,
)


@pytest.mark.asyncio
async def test_async_export_profiles(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)

    async def fake_load_all(_hass):
        return {
            "p1": {
                "plant_id": "p1",
                "display_name": "Plant 1",
                "resolved_targets": {
                    "temp": {
                        "value": 20,
                        "annotation": {"source_type": "manual"},
                        "citations": [],
                    }
                },
            }
        }

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.export.async_load_all",
        fake_load_all,
    )
    path = await async_export_profiles(hass, "profiles.json")
    assert Path(path) == tmp_path / "profiles.json"
    data = json.loads(Path(path).read_text())
    assert data["p1"]["resolved_targets"]["temp"]["value"] == 20
    assert data["p1"]["library"]["profile_id"] == "p1"
    assert data["p1"]["local"]["general"] == {}
    assert "sections" in data["p1"]


@pytest.mark.asyncio
async def test_async_export_profile(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)

    async def fake_get_profile(_hass, pid):
        if pid == "p1":
            return {
                "plant_id": "p1",
                "display_name": "Plant 1",
                "resolved_targets": {
                    "temp": {
                        "value": 20,
                        "annotation": {"source_type": "manual"},
                        "citations": [],
                    }
                },
            }
        return None

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.export.async_get_profile",
        fake_get_profile,
    )

    path = await async_export_profile(hass, "p1", "one.json")
    assert Path(path) == tmp_path / "one.json"
    data = json.loads(Path(path).read_text())
    assert data["plant_id"] == "p1"
    assert data["library"]["profile_id"] == "p1"
    assert data["local"]["general"] == {}
    assert "sections" in data

    with pytest.raises(ValueError):
        await async_export_profile(hass, "missing", "missing.json")
