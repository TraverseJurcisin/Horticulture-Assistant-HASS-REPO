import json
import types
from typing import Any

import pytest

from custom_components.horticulture_assistant.profile.schema import (
    BioProfile,
    Citation,
    FieldAnnotation,
    ProfileLibrarySection,
    ProfileLocalSection,
    ResolvedTarget,
)
from custom_components.horticulture_assistant.profile.store import (
    async_save_profile_from_options,
)
from custom_components.horticulture_assistant.profile_store import ProfileStore


@pytest.mark.asyncio
async def test_async_create_profile_inherits_sensors_from_existing_profile(hass, tmp_path, monkeypatch) -> None:
    """Profiles cloned from storage should inherit sensor bindings and metadata."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_profile = BioProfile(
        profile_id="base_profile",
        display_name="Base Profile",
        resolved_targets={"temp": ResolvedTarget(value=20, annotation=FieldAnnotation(source_type="manual"))},
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
    assert clone["sections"]["resolved"]["thresholds"]["temp"] == 20


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
    assert clone["sections"]["resolved"]["thresholds"]["ec"] == 1.2


@pytest.mark.asyncio
async def test_async_create_profile_ignores_blank_sensor_entries(hass, tmp_path, monkeypatch) -> None:
    """Provided sensor mappings should skip blank or ``None`` values."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_create_profile(
        "Filtered Sensors",
        sensors={
            "moisture": None,
            "temperature": "",
            "illuminance": "  sensor.light  ",
        },
    )

    profile = await store.async_get("Filtered Sensors")
    assert profile is not None
    assert profile["sensors"] == {"illuminance": "sensor.light"}
    general = profile["general"] if isinstance(profile.get("general"), dict) else {}
    assert general.get("sensors") == {"illuminance": "sensor.light"}


@pytest.mark.asyncio
async def test_async_list_returns_human_readable_names(hass, tmp_path, monkeypatch) -> None:
    """Listing profiles should return stored display names when available."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save(
        BioProfile(
            profile_id="fancy_basil",
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
    assert "sections" in data


@pytest.mark.asyncio
async def test_async_get_handles_corrupt_profile(hass, tmp_path, monkeypatch) -> None:
    """Corrupted on-disk profiles should be treated as missing."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    broken_path = store._path_for("Broken Plant")
    broken_path.write_text("{not-json", encoding="utf-8")

    assert await store.async_get("Broken Plant") is None


@pytest.mark.asyncio
async def test_async_save_profile_from_options_preserves_local_sections(hass, tmp_path, monkeypatch) -> None:
    """Saving from options should materialise library/local sections."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    saved: dict[str, dict[str, Any]] = {}

    class DummyStore:
        async def async_save(self, data):
            saved.update(data)

        async def async_load(self):
            return saved

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store._store",
        lambda _hass: DummyStore(),
    )

    entry = types.SimpleNamespace(
        options={
            "profiles": {
                "p1": {
                    "name": "Plant",
                    "thresholds": {"temp_c_min": 5.0},
                    "sources": {"temp_c_min": {"mode": "manual", "value": 5.0}},
                    "citations": {
                        "temp_c_min": {
                            "mode": "manual",
                            "source_detail": "Manual entry",
                            "ts": "2025-01-01T00:00:00Z",
                        }
                    },
                    "library": ProfileLibrarySection(
                        profile_id="p1",
                        profile_type="line",
                        curated_targets={"temp_c_min": 3.0},
                    ).to_json(),
                    "local": ProfileLocalSection(
                        general={"note": "local"},
                        resolver_state={
                            "sources": {"temp_c_min": {"mode": "manual"}},
                            "resolved_keys": ["temp_c_min"],
                        },
                        citations=[
                            Citation(
                                source="manual",
                                title="Manual temp",
                                details={"field": "temp_c_min"},
                                accessed="2025-01-01T00:00:00Z",
                            )
                        ],
                        metadata={
                            "citation_map": {
                                "temp_c_min": {
                                    "mode": "manual",
                                    "source_detail": "Manual entry",
                                    "ts": "2025-01-01T00:00:00Z",
                                }
                            }
                        },
                        last_resolved="2025-01-01T00:00:00Z",
                    ).to_json(),
                }
            }
        }
    )

    await async_save_profile_from_options(hass, entry, "p1")
    await hass.async_block_till_done()
    profile = saved.get("p1")
    assert profile is not None
    assert profile["sections"]["resolved"]["thresholds"]["temp_c_min"] == 5.0
    local = BioProfile.from_json(profile).local_section()
    assert local.metadata["citation_map"]["temp_c_min"]["mode"] == "manual"
    assert local.citations and local.citations[0].source == "manual"
