import json

import pytest

from custom_components.horticulture_assistant.profile.importer import (
    async_import_profiles,
)


@pytest.mark.asyncio
async def test_async_import_profiles_overwrites(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    saved: dict[str, dict] = {
        "p1": {
            "plant_id": "p1",
            "display_name": "Old",
            "variables": {},
        }
    }

    async def fake_save_profile(_hass, profile):
        saved[profile["plant_id"]] = profile

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.importer.async_save_profile",
        fake_save_profile,
    )

    data = {
        "p1": {
            "plant_id": "p1",
            "display_name": "New Name",
            "variables": {},
        }
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(data))

    count = await async_import_profiles(hass, "profiles.json")
    assert count == 1
    assert saved["p1"]["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_async_import_profiles_supports_list(tmp_path, monkeypatch, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    saved: list[dict] = []

    async def fake_save_profile(_hass, profile):
        saved.append(profile)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.importer.async_save_profile",
        fake_save_profile,
    )

    data = [
        {
            "plant_id": "p1",
            "display_name": "Plant 1",
            "variables": {},
        },
        {
            "plant_id": "p2",
            "display_name": "Plant 2",
            "variables": {},
        },
    ]
    path = tmp_path / "profiles_list.json"
    path.write_text(json.dumps(data))

    count = await async_import_profiles(hass, "profiles_list.json")
    assert count == 2
    assert {p["plant_id"] for p in saved} == {"p1", "p2"}


@pytest.mark.asyncio
async def test_async_import_profiles_bad_json(tmp_path, hass):
    hass.config.path = lambda p: str(tmp_path / p)
    path = tmp_path / "bad.json"
    path.write_text("not json")

    with pytest.raises(ValueError):
        await async_import_profiles(hass, "bad.json")
