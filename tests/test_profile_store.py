import json

import pytest

from custom_components.horticulture_assistant.profile.schema import (
    FieldAnnotation,
    PlantProfile,
    ResolvedTarget,
)
from custom_components.horticulture_assistant.profile_store import ProfileStore


@pytest.mark.asyncio
async def test_async_create_profile_inherits_sensors_from_existing_profile(hass, tmp_path, monkeypatch) -> None:
    """Profiles cloned from storage should inherit sensor bindings and metadata."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_profile = PlantProfile(
        plant_id="base_profile",
        display_name="Base Profile",
        resolved_targets={
            "temp": ResolvedTarget(value=20, annotation=FieldAnnotation(source_type="manual"))
        },
        general={"sensors": {"temp": "sensor.base"}},
    )
    await store.async_save(base_profile, name="base_profile")

    await store.async_create_profile("Clone Profile", clone_from="base_profile")

    clone = await store.async_get("Clone Profile")
    assert clone is not None
    assert clone["sensors"] == {"temp": "sensor.base"}
    assert clone["resolved_targets"]["temp"]["value"] == 20
    assert clone["resolved_targets"]["temp"]["annotation"]["source_type"] == "manual"
    assert clone["library"]["profile_id"] == clone["plant_id"]
    assert clone["local"]["general"]["sensors"]["temp"] == "sensor.base"


@pytest.mark.asyncio
async def test_async_create_profile_clones_sensors_from_dict_payload(hass, tmp_path, monkeypatch) -> None:
    """Cloning from a raw payload must copy sensor and resolved target data."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    source_payload = {
        "display_name": "Source",
        "sensors": {"ec": "sensor.clone"},
        "thresholds": {"ec": 1.2},
    }

    await store.async_create_profile("Payload Clone", clone_from=source_payload)

    # Mutate the source after cloning to ensure data was copied.
    source_payload["sensors"]["ec"] = "sensor.mutated"
    source_payload["thresholds"]["ec"] = 3.4

    clone = await store.async_get("Payload Clone")
    assert clone is not None
    assert clone["sensors"] == {"ec": "sensor.clone"}
    assert clone["resolved_targets"]["ec"]["value"] == 1.2
    assert clone["variables"]["ec"]["value"] == 1.2
    assert clone["library"]["profile_id"] == clone["plant_id"]
    assert clone["local"]["general"]["sensors"]["ec"] == "sensor.clone"


@pytest.mark.asyncio
async def test_async_list_returns_human_readable_names(hass, tmp_path, monkeypatch) -> None:
    """Listing profiles should return stored display names when available."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save(
        PlantProfile(
            plant_id="fancy_basil",
            display_name="Fancy Basil",
        ),
        name="Fancy Basil",
    )

    # Write a malformed profile file to ensure we gracefully fall back to the slug.
    broken_path = store._path_for("Broken Plant")
    broken_path.write_text("{not-json", encoding="utf-8")

    names = await store.async_list()

    assert "Fancy Basil" in names
    assert broken_path.stem in names

    # Sanity check that the saved profile is stored as valid JSON.
    saved_path = store._path_for("Fancy Basil")
    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert data["display_name"] == "Fancy Basil"
    assert data["thresholds"] == {}
    assert data["library"]["profile_id"] == data["plant_id"]
    assert data["local"]["general"] == {}
