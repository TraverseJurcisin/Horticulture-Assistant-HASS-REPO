import json

import pytest

from custom_components.horticulture_assistant.profile.importer import (
    async_import_profiles,
)
from custom_components.horticulture_assistant.profile.schema import PlantProfile


@pytest.mark.asyncio
async def test_async_import_profiles_overwrites(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    saved: dict[str, dict] = {
        "p1": {
            "plant_id": "p1",
            "display_name": "Old",
            "resolved_targets": {},
        }
    }

    async def fake_save_profile(_hass, profile):
        if isinstance(profile, PlantProfile):
            payload = profile.to_json()
        else:
            payload = profile
        saved[payload["plant_id"]] = payload

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.importer.async_save_profile",
        fake_save_profile,
    )

    data = {
        "p1": {
            "plant_id": "p1",
            "display_name": "New Name",
            "resolved_targets": {},
        }
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(data))

    count = await async_import_profiles(hass, "profiles.json")
    assert count == 1
    assert saved["p1"]["display_name"] == "New Name"
    assert saved["p1"]["library"]["profile_id"] == "p1"
    assert saved["p1"]["local"]["general"] == {}


@pytest.mark.asyncio
async def test_async_import_profiles_supports_list(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    saved: list[dict] = []

    async def fake_save_profile(_hass, profile):
        if isinstance(profile, PlantProfile):
            payload = profile.to_json()
        else:
            payload = profile
        saved.append(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.importer.async_save_profile",
        fake_save_profile,
    )

    data = [
        {
            "plant_id": "p1",
            "display_name": "Plant 1",
            "resolved_targets": {},
        },
        {
            "plant_id": "p2",
            "display_name": "Plant 2",
            "resolved_targets": {},
        },
    ]
    path = tmp_path / "profiles_list.json"
    path.write_text(json.dumps(data))

    count = await async_import_profiles(hass, "profiles_list.json")
    assert count == 2
    assert {p["plant_id"] for p in saved} == {"p1", "p2"}
    assert all("library" in p and "local" in p for p in saved)


@pytest.mark.asyncio
async def test_async_import_profiles_bad_json(tmp_path, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    path = tmp_path / "bad.json"
    path.write_text("not json")

    with pytest.raises(ValueError):
        await async_import_profiles(hass, "bad.json")
