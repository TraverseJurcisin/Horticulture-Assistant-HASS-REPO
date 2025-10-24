import json
import types
from typing import Any

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

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
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry
from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.profile import store as profile_store


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


@pytest.mark.asyncio
async def test_record_harvest_event_publishes_species_profile(hass) -> None:
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()

    published: list[str] = []

    def _capture(self, profile):
        published.append(profile.profile_id)

    registry._cloud_publish_profile = types.MethodType(_capture, registry)

    await registry.async_record_harvest_event(
        "cultivar.1",
        {
            "harvest_id": "harvest-1",
            "harvested_at": "2024-05-01T00:00:00Z",
            "yield_grams": 50.0,
        },
    )

    assert any(pid == "cultivar.1" for pid in published)
    assert "species.1" in published
