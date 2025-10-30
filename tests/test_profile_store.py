import json
import types
from copy import deepcopy
from typing import Any

import pytest

from custom_components.horticulture_assistant.const import CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT
from custom_components.horticulture_assistant.profile.schema import (
    BioProfile,
    Citation,
    CultivarProfile,
    FieldAnnotation,
    ProfileLibrarySection,
    ProfileLocalSection,
    ResolvedTarget,
)
from custom_components.horticulture_assistant.profile.store import (
    CACHE_KEY,
    async_delete_profile,
    async_load_all,
    async_save_profile,
    async_save_profile_from_options,
)
from custom_components.horticulture_assistant.profile_store import (
    LOCAL_RELATIVE_PATH,
    PROFILES_DIRNAME,
    ProfileStore,
)


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


@pytest.mark.parametrize(
    ("candidate", "expected"),
    (
        ("foo/bar", "foo_bar"),
        ("foo\\bar", "foo_bar"),
        ("../config/plant", "config_plant"),
    ),
)
def test_safe_slug_normalises_all_path_segments(candidate: str, expected: str) -> None:
    """Normalised slugs should retain all path segments instead of truncating."""

    assert ProfileStore._normalise_slug_component(candidate) == expected


@pytest.mark.asyncio
async def test_async_create_profile_preserves_sequence_sensor_bindings(hass, tmp_path, monkeypatch) -> None:
    """Sensor sequences from a cloned profile should retain all entries."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_profile = BioProfile(
        profile_id="sequence_profile",
        display_name="Sequence Profile",
        resolved_targets={
            "moisture": ResolvedTarget(value=55, annotation=FieldAnnotation(source_type="manual")),
            "temperature": ResolvedTarget(value=18, annotation=FieldAnnotation(source_type="manual")),
        },
        general={
            "sensors": {
                "moisture": [" sensor.one ", "sensor.two", ""],
                "temperature": (" sensor.temp ",),
            }
        },
    )
    await store.async_save(base_profile, name="sequence_profile")

    await store.async_create_profile("Sequence Clone", clone_from="sequence_profile")

    clone = await store.async_get("Sequence Clone")
    assert clone is not None
    assert clone["sensors"] == {
        "moisture": ["sensor.one", "sensor.two"],
        "temperature": ["sensor.temp"],
    }
    general = clone["general"] if isinstance(clone.get("general"), dict) else {}
    assert general.get("sensors") == {
        "moisture": ["sensor.one", "sensor.two"],
        "temperature": ["sensor.temp"],
    }


@pytest.mark.asyncio
async def test_async_create_profile_can_clear_cloned_sensors(hass, tmp_path, monkeypatch) -> None:
    """Explicit sensor parameters should remove cloned bindings when empty."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_profile = BioProfile(
        profile_id="sensors_base",
        display_name="Sensors Base",
        general={"sensors": {"moisture": "sensor.old"}},
    )
    base_profile.refresh_sections()
    await store.async_save(base_profile, name="Sensors Base")

    await store.async_create_profile("Sensors Cleared", clone_from="Sensors Base", sensors={})

    cleared = await store.async_get("Sensors Cleared")
    assert cleared is not None
    assert cleared.get("sensors") in (None, {})
    general = cleared.get("general") if isinstance(cleared.get("general"), dict) else {}
    assert general.get("sensors") in (None, {})


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
async def test_async_create_profile_accepts_sequence_sensor_parameters(hass, tmp_path, monkeypatch) -> None:
    """Profile creation should handle list or tuple sensor inputs."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_create_profile(
        "Sequence Inputs",
        sensors={
            "moisture": [" sensor.one ", "sensor.two", ""],
            "temperature": (" sensor.temp ",),
            "illuminance": " sensor.light ",
            "set_role": {" sensor.alpha ", "sensor.beta"},
            "invalid": [],
            "none": None,
        },
    )

    profile = await store.async_get("Sequence Inputs")
    assert profile is not None
    assert profile["sensors"] == {
        "moisture": ["sensor.one", "sensor.two"],
        "temperature": ["sensor.temp"],
        "illuminance": "sensor.light",
        "set_role": ["sensor.alpha", "sensor.beta"],
    }
    general = profile["general"] if isinstance(profile.get("general"), dict) else {}
    assert general.get("sensors") == {
        "moisture": ["sensor.one", "sensor.two"],
        "temperature": ["sensor.temp"],
        "illuminance": "sensor.light",
        "set_role": ["sensor.alpha", "sensor.beta"],
    }


@pytest.mark.asyncio
async def test_async_list_handles_corrupted_payload(hass, tmp_path, monkeypatch) -> None:
    """Corrupted profile files should not prevent listing remaining entries."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_dir = tmp_path / LOCAL_RELATIVE_PATH / PROFILES_DIRNAME
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "broken.json").write_text(
        json.dumps({"display_name": "Broken", "library": {"parents": 5}}),
        encoding="utf-8",
    )

    names = await store.async_list()

    assert names == ["broken"]

    profile = await store.async_get("broken")

    assert profile is None


@pytest.mark.asyncio
async def test_async_create_profile_normalises_scope(hass, tmp_path, monkeypatch) -> None:
    """Scopes should normalise to recognised values or defaults."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_create_profile("Default Scope", scope="   ")
    profile = await store.async_get("Default Scope")
    general = profile["general"] if isinstance(profile.get("general"), dict) else {}
    assert general.get(CONF_PROFILE_SCOPE) == PROFILE_SCOPE_DEFAULT

    base = BioProfile(
        profile_id="scope_source",
        display_name="Scope Source",
        general={CONF_PROFILE_SCOPE: "crop_batch"},
    )
    await store.async_save(base, name="scope_source")
    await store.async_create_profile("Clone Scope", clone_from="scope_source", scope="invalid")
    cloned = await store.async_get("Clone Scope")
    clone_general = cloned["general"] if isinstance(cloned.get("general"), dict) else {}
    assert clone_general.get(CONF_PROFILE_SCOPE) == "crop_batch"

    await store.async_create_profile("Case Scope", scope="Grow_Zone")
    case_profile = await store.async_get("Case Scope")
    case_general = case_profile["general"] if isinstance(case_profile.get("general"), dict) else {}
    assert case_general.get(CONF_PROFILE_SCOPE) == "grow_zone"


@pytest.mark.asyncio
async def test_async_create_profile_preserves_opb_credentials(hass, tmp_path, monkeypatch) -> None:
    """Profiles cloned from storage should retain OpenPlantbook credentials."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save(
        {
            "display_name": "Source",  # Stored payload includes credentials and sensor metadata
            "profile_id": "source",
            "plant_id": "source",
            "general": {"sensors": {"ec": "sensor.ec"}},
            "sensors": {"ec": "sensor.ec"},
            "thresholds": {"ec": 1.23},
            "opb_credentials": {"client_id": "id", "secret": "sec"},
        },
        name="Source",
    )

    await store.async_create_profile("Clone", clone_from="Source")

    clone = await store.async_get("Clone")
    assert clone is not None
    assert clone["opb_credentials"] == {"client_id": "id", "secret": "sec"}


@pytest.mark.asyncio
async def test_profile_store_preserves_numeric_species_pid(hass, tmp_path, monkeypatch) -> None:
    """Numeric Plantbook identifiers should be preserved when saving or cloning profiles."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save(
        {
            "display_name": "Numeric Base",
            "profile_id": "numeric_base",
            "plant_id": "numeric_base",
            "species_display": "Tomato",
            "species_pid": 987654,
        },
        name="Numeric Base",
    )

    stored = await store.async_get("Numeric Base")
    assert stored is not None
    assert stored["species_pid"] == "987654"
    assert stored["species_display"] == "Tomato"

    await store.async_create_profile("Numeric Clone", clone_from="Numeric Base")

    clone = await store.async_get("Numeric Clone")
    assert clone is not None
    assert clone["species_pid"] == "987654"
    assert clone["species_display"] == "Tomato"


@pytest.mark.asyncio
async def test_async_create_profile_handles_mapping_credentials(hass, tmp_path, monkeypatch) -> None:
    """Cloning should normalise mapping-proxy credentials for JSON storage."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    credentials = types.MappingProxyType({"client_id": "id", "secret": "sec"})
    await store.async_create_profile(
        "Proxy Clone",
        clone_from={
            "display_name": "Proxy Clone",
            "opb_credentials": credentials,
        },
    )

    clone = await store.async_get("Proxy Clone")
    assert clone is not None
    assert clone["opb_credentials"] == {"client_id": "id", "secret": "sec"}


@pytest.mark.asyncio
async def test_async_create_profile_preserves_cultivar_specific_fields(hass, tmp_path, monkeypatch) -> None:
    """Cloning a cultivar profile should retain subclass-specific metadata."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    base_profile = CultivarProfile(
        profile_id="cultivar_base",
        display_name="Cultivar Base",
        area_m2=4.2,
        general={"sensors": {"temp": "sensor.source"}},
    )
    base_profile.refresh_sections()
    await store.async_save(base_profile, name="Cultivar Base")

    await store.async_create_profile("Cultivar Clone", clone_from="Cultivar Base")

    clone = await store.async_get("Cultivar Clone")
    assert clone is not None
    assert clone["profile_type"] == "cultivar"
    assert clone["area_m2"] == 4.2


@pytest.mark.asyncio
async def test_async_save_preserves_mapping_credentials(hass, tmp_path, monkeypatch) -> None:
    """Saving payloads with mapping-proxy credentials should keep the secrets."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    payload = {
        "display_name": "Proxy Source",
        "opb_credentials": types.MappingProxyType({"client_id": "id", "secret": "sec"}),
    }

    await store.async_save(payload, name="Proxy Source")

    stored = await store.async_get("Proxy Source")
    assert stored is not None
    assert stored["opb_credentials"] == {"client_id": "id", "secret": "sec"}


@pytest.mark.asyncio
async def test_async_save_prefers_profile_id_for_storage_name(hass, tmp_path, monkeypatch) -> None:
    """Saving a payload without a name should fall back to the profile id."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save({"profile_id": "unique_profile"})

    expected_path = store._path_for("unique_profile")
    assert expected_path.exists(), "Profile should be saved under its profile_id slug"

    saved = json.loads(expected_path.read_text(encoding="utf-8"))
    assert saved["profile_id"] == "unique_profile"

    fallback_path = store._path_for("profile")
    if fallback_path != expected_path:
        assert not fallback_path.exists(), "Default fallback file should not be created"


@pytest.mark.asyncio
async def test_path_for_disallows_path_traversal(hass, tmp_path, monkeypatch) -> None:
    """Profile paths must be constrained to the storage directory."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    outside = store._path_for("../sneaky")
    assert outside.parent == store._base
    assert outside.name == "sneaky.json"

    dotdot = store._path_for("../../")
    assert dotdot.parent == store._base
    assert dotdot.name == "profile.json"


@pytest.mark.asyncio
async def test_path_for_rewrites_windows_reserved_names(hass, tmp_path, monkeypatch) -> None:
    """Reserved Windows device names should be rewritten to safe slugs."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    con_path = store._path_for("CON")
    assert con_path.name == "con_profile.json"

    com_path = store._path_for("Com1")
    assert com_path.name == "com1_profile.json"

    aux_suffix = store._path_for("aux.report")
    assert aux_suffix.name == "aux_profile_report.json"

    aux_multi_suffix = store._path_for("aux.backup.json")
    assert aux_multi_suffix.name == "aux_profile_backup_json.json"


@pytest.mark.asyncio
async def test_path_for_removes_embedded_extension(hass, tmp_path, monkeypatch) -> None:
    """Profile names containing extensions should not duplicate the file suffix."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    json_path = store._path_for("profile.json")
    assert json_path.name == "profile_json.json"

    nested_path = store._path_for("layout.config.backup")
    assert nested_path.name == "layout_config_backup.json"


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
async def test_async_list_handles_invalid_utf8_profile(hass, tmp_path, monkeypatch) -> None:
    """Profiles with invalid encodings should not break listing."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    bad_path = store._path_for("Invalid UTF8")
    bad_path.write_bytes(b"\xff\xfe\xfd")

    names = await store.async_list()

    assert bad_path.stem in names


@pytest.mark.asyncio
async def test_async_get_handles_invalid_utf8_profile(hass, tmp_path, monkeypatch) -> None:
    """Profiles with invalid encodings should be treated as missing."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    bad_path = store._path_for("Invalid UTF8")
    bad_path.write_bytes(b"\xff\xfe\xfd")

    assert await store.async_get("Invalid UTF8") is None


@pytest.mark.asyncio
async def test_async_get_handles_non_mapping_payload(hass, tmp_path, monkeypatch) -> None:
    """Profiles stored as non-mapping JSON should be ignored."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    broken_path = store._path_for("Broken Plant")
    broken_path.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")

    assert await store.async_get("Broken Plant") is None

    names = await store.async_list()
    assert broken_path.stem in names


@pytest.mark.asyncio
async def test_async_get_filters_invalid_resolved_target_citations(hass, tmp_path, monkeypatch) -> None:
    """Resolved target citations must ignore malformed entries instead of failing."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    payload = {
        "profile_id": "citations_profile",
        "display_name": "Citations Profile",
        "resolved_targets": {
            "ph": {
                "value": 6.2,
                "annotation": {"source_type": "manual"},
                "citations": [
                    {"source": "manual", "title": "Valid citation"},
                    "invalid",
                    42,
                ],
            }
        },
    }

    bad_path = store._path_for("Citations Profile")
    bad_path.write_text(json.dumps(payload), encoding="utf-8")

    profile = await store.async_get("Citations Profile")
    assert profile is not None

    target = profile["resolved_targets"]["ph"]
    assert target["value"] == 6.2
    assert len(target.get("citations", [])) == 1
    assert target["citations"][0]["source"] == "manual"


@pytest.mark.asyncio
async def test_async_save_handles_numeric_identifiers(hass, tmp_path, monkeypatch) -> None:
    """Profiles with numeric ids should be stored without raising errors."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save({"plant_id": 987, "profile_id": 987})

    saved = await store.async_get("987")
    assert saved is not None
    assert saved["plant_id"] == "987"
    assert saved["display_name"] == "987"


@pytest.mark.asyncio
async def test_async_save_defaults_plant_id_to_profile_id(hass, tmp_path, monkeypatch) -> None:
    """Profiles missing a plant_id should inherit it from the profile_id."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_save({"profile_id": "existing", "display_name": "My Plant"})

    saved = await store.async_get("My Plant")
    assert saved is not None
    assert saved["profile_id"] == "existing"
    assert saved["plant_id"] == "existing"


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
async def test_async_load_all_handles_non_mapping_storage(hass, monkeypatch) -> None:
    """Storage corruption should not blow up the loader."""

    cached_payload = {"cached": {"display_name": "Cached"}}
    hass.data[CACHE_KEY] = deepcopy(cached_payload)

    class DummyStore:
        async def async_load(self):
            return ["not", "a", "mapping"]

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store._store",
        lambda _hass: DummyStore(),
    )

    result = await async_load_all(hass)
    assert result == cached_payload
    assert result is not hass.data[CACHE_KEY]
    assert result["cached"] is not hass.data[CACHE_KEY]["cached"]

    hass.data[CACHE_KEY].clear()
    result_no_cache = await async_load_all(hass)
    assert result_no_cache == {}


@pytest.mark.asyncio
async def test_async_load_all_respects_empty_storage(hass, monkeypatch) -> None:
    """An explicit empty payload from storage should clear the cache."""

    hass.data[CACHE_KEY] = {"cached": {"display_name": "Cached"}}

    class DummyStore:
        async def async_load(self):
            return {}

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store._store",
        lambda _hass: DummyStore(),
    )

    result = await async_load_all(hass)

    assert result == {}
    assert hass.data[CACHE_KEY] == {}


@pytest.mark.asyncio
async def test_async_delete_profile_refreshes_cache(hass, tmp_path, monkeypatch) -> None:
    """Removing profiles from storage should also evict them from the in-memory cache."""

    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    payload = {"profile_id": "plant", "display_name": "Plant"}

    await async_save_profile(hass, payload)
    await async_load_all(hass)

    cache = hass.data.get(CACHE_KEY)
    assert cache is not None and "plant" in cache

    await async_delete_profile(hass, "plant")

    cache = hass.data.get(CACHE_KEY)
    assert cache is not None and "plant" not in cache
