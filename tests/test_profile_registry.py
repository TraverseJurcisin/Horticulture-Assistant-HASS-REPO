import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.cloudsync.edge_store import EdgeSyncStore
from custom_components.horticulture_assistant.cloudsync.manager import CloudSyncConfig
from custom_components.horticulture_assistant.cloudsync.publisher import CloudSyncPublisher
from custom_components.horticulture_assistant.const import (
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
)
from custom_components.horticulture_assistant.profile import store as profile_store
from custom_components.horticulture_assistant.profile.schema import BioProfile, SpeciesProfile
from custom_components.horticulture_assistant.profile.statistics import (
    EVENT_STATS_VERSION,
    NUTRIENT_STATS_VERSION,
)
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry

pytestmark = pytest.mark.asyncio


async def _make_entry(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {})
    entry.add_to_hass(hass)
    return entry


async def test_initialize_merges_storage_and_options(hass):
    """Profiles in storage and options are merged."""

    prof = BioProfile(profile_id="p1", display_name="Stored")
    await profile_store.async_save_profile(hass, prof)

    entry = await _make_entry(hass, {CONF_PROFILES: {"p2": {"name": "Opt"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    ids = {p.profile_id for p in reg.list_profiles()}
    assert ids == {"p1", "p2"}
    assert reg.get("p2").display_name == "Opt"


async def test_async_load_migrates_list_format(hass):
    """Registry converts legacy list storage to dict mapping."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    with patch.object(reg._store, "async_load", return_value=[{"plant_id": "legacy", "display_name": "Legacy"}]):
        await reg.async_load()

    prof = reg.get("legacy")
    assert prof and prof.display_name == "Legacy"


async def test_async_load_merges_option_sensors_overrides_storage(hass):
    """Sensors from config entry options override stored mappings."""

    stored = BioProfile(profile_id="p1", display_name="Stored")
    stored.general["sensors"] = {"temperature": "sensor.old", "moisture": "sensor.m"}
    await profile_store.async_save_profile(hass, stored)

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Stored",
                    "sensors": {"temperature": "sensor.new", "humidity": "sensor.h"},
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    prof = reg.get("p1")
    assert prof is not None
    assert prof.general["sensors"] == {
        "temperature": "sensor.new",
        "moisture": "sensor.m",
        "humidity": "sensor.h",
    }
    assert prof.general["sensors"] is not entry.options[CONF_PROFILES]["p1"]["sensors"]


async def test_replace_sensor_updates_entry_and_registry(hass):
    """Replacing a sensor updates both entry options and registry state."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", "sensor.temp")

    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["temperature"] == "sensor.temp"
    prof = reg.get("p1")
    assert prof.general["sensors"]["temperature"] == "sensor.temp"
    sections = entry.options[CONF_PROFILES]["p1"].get("sections", {})
    assert sections["local"]["general"]["sensors"]["temperature"] == "sensor.temp"
    refreshed_local = prof.refresh_sections().local
    assert refreshed_local.general["sensors"]["temperature"] == "sensor.temp"


async def test_replace_sensor_unknown_profile_raises(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    with pytest.raises(ValueError):
        await reg.async_replace_sensor("missing", "temperature", "sensor.temp")


async def test_refresh_species_marks_profile(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_refresh_species("p1")
    prof = reg.get("p1")
    assert prof.last_resolved == "1970-01-01T00:00:00Z"


async def test_refresh_species_unknown_profile(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    with pytest.raises(ValueError):
        await reg.async_refresh_species("bad")


async def test_export_creates_file_with_profiles(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    path = tmp_path / "profiles.json"
    out = await reg.async_export(path)
    assert out == path
    assert path.exists()
    data = json.loads(path.read_text())
    assert data[0]["display_name"] == "Plant"


async def test_summaries_return_serialisable_data(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "humidity", "sensor.h")
    summaries = reg.summaries()
    assert summaries == [
        {
            "plant_id": "p1",
            "name": "Plant",
            "profile_type": "line",
            "species": None,
            "tenant_id": None,
            "parents": [],
            "sensors": {"humidity": "sensor.h"},
            "targets": {},
            "tags": [],
            "last_resolved": None,
        }
    ]


async def test_iteration_and_len(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert len(reg) == 1
    assert [p.profile_id for p in reg] == ["p1"]


async def test_multiple_sensor_replacements(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", "sensor.t1")
    await reg.async_replace_sensor("p1", "humidity", "sensor.h1")
    await reg.async_replace_sensor("p1", "temperature", "sensor.t2")

    sensors = entry.options[CONF_PROFILES]["p1"]["sensors"]
    assert sensors == {"temperature": "sensor.t2", "humidity": "sensor.h1"}
    prof = reg.get("p1")
    assert prof.general["sensors"] == sensors


async def test_record_run_event_appends_and_persists(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    result = await reg.async_record_run_event(
        "cultivar.1",
        {"run_id": "run-1", "started_at": "2024-01-01T00:00:00Z"},
    )

    profile = reg.get("cultivar.1")
    assert profile is not None
    assert len(profile.run_history) == 1
    assert result.profile_id == "cultivar.1"
    assert profile.run_history[0].species_id == "species.1"
    assert profile.updated_at is not None

    stored = await profile_store.async_load_profile(hass, "cultivar.1")
    assert stored is not None and len(stored.run_history) == 1


async def test_record_harvest_event_updates_statistics(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_record_run_event(
        "cultivar.1",
        {
            "run_id": "run-1",
            "started_at": "2024-01-01T00:00:00Z",
            "ended_at": "2024-01-06T00:00:00Z",
            "environment": {"temperature_c": 23.5, "humidity_percent": 55},
        },
    )
    event = await reg.async_record_harvest_event(
        "cultivar.1",
        {
            "harvest_id": "harvest-1",
            "harvested_at": "2024-02-01T00:00:00Z",
            "yield_grams": 125.5,
            "area_m2": 2.5,
        },
    )

    cultivar_prof = reg.get("cultivar.1")
    assert cultivar_prof is not None
    assert len(cultivar_prof.harvest_history) == 1
    assert event.run_id == "run-1"
    assert cultivar_prof.statistics and cultivar_prof.statistics[0].scope == "cultivar"
    metrics = cultivar_prof.statistics[0].metrics
    assert metrics["total_yield_grams"] == 125.5
    assert metrics["average_yield_density_g_m2"] == round(125.5 / 2.5, 3)
    cultivar_snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert cultivar_snapshot is not None
    assert cultivar_snapshot.payload["yields"]["total_grams"] == pytest.approx(125.5)
    assert cultivar_snapshot.payload["runs_tracked"] == 1

    species_prof = reg.get("species.1")
    assert species_prof is not None
    species_metrics = species_prof.statistics[0].metrics
    assert species_metrics["total_yield_grams"] == 125.5
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert species_snapshot is not None
    contributors = {item["profile_id"]: item for item in species_snapshot.payload["contributors"]}
    assert contributors["cultivar.1"]["total_yield_grams"] == pytest.approx(125.5)

    stored_cultivar = await profile_store.async_load_profile(hass, "cultivar.1")
    assert stored_cultivar is not None and len(stored_cultivar.harvest_history) == 1
    stored_snapshot = next(
        (snap for snap in stored_cultivar.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert stored_snapshot is not None

    cultivar_env = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert cultivar_env is not None
    assert cultivar_env.payload["metrics"]["avg_temperature_c"] == pytest.approx(23.5)
    assert cultivar_env.payload["runs_recorded"] == 1

    species_env = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert species_env is not None
    assert species_env.payload["runs_recorded"] >= 1


async def test_record_nutrient_event_updates_snapshots(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    event = await reg.async_record_nutrient_event(
        "cultivar.1",
        {
            "event_id": "feed-1",
            "applied_at": "2024-03-01T08:00:00Z",
            "product_id": "fert-001",
            "product_name": "Grow A",
            "solution_volume_liters": 12.5,
            "concentration_ppm": 850,
        },
    )

    cultivar_prof = reg.get("cultivar.1")
    assert cultivar_prof is not None
    assert len(cultivar_prof.nutrient_history) == 1
    assert event.product_name == "Grow A"
    snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == NUTRIENT_STATS_VERSION),
        None,
    )
    assert snapshot is not None
    metrics = snapshot.payload["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)
    assert metrics["total_volume_liters"] == pytest.approx(12.5)
    assert snapshot.payload["last_event"]["product_name"] == "Grow A"

    species_prof = reg.get("species.1")
    assert species_prof is not None
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == NUTRIENT_STATS_VERSION),
        None,
    )
    assert species_snapshot is not None
    assert species_snapshot.payload["metrics"]["total_events"] == pytest.approx(1.0)
    contributors = species_snapshot.payload.get("contributors") or []
    assert any(item.get("profile_id") == "cultivar.1" for item in contributors)

    stored = await profile_store.async_load_profile(hass, "cultivar.1")
    assert stored is not None and len(stored.nutrient_history) == 1


async def test_record_cultivation_event_updates_statistics(hass):
    species = BioProfile(profile_id="species.2", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.2",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.2",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    event = await reg.async_record_cultivation_event(
        "cultivar.2",
        {
            "event_id": "evt-1",
            "occurred_at": "2024-04-01T09:30:00Z",
            "event_type": "pruning",
            "title": "Canopy prune",
            "notes": "Removed lower leaves",
            "metric_value": 3.2,
            "metric_unit": "cm",
        },
    )

    cultivar_prof = reg.get("cultivar.2")
    assert cultivar_prof is not None
    assert len(cultivar_prof.event_history) == 1
    assert event.event_type == "pruning"
    snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == EVENT_STATS_VERSION),
        None,
    )
    assert snapshot is not None
    metrics = snapshot.payload["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)
    assert snapshot.payload["last_event"]["title"] == "Canopy prune"

    species_prof = reg.get("species.2")
    assert species_prof is not None
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == EVENT_STATS_VERSION),
        None,
    )
    assert species_snapshot is not None
    species_metrics = species_snapshot.payload["metrics"]
    assert species_metrics["total_events"] == pytest.approx(1.0)
    contributors = species_snapshot.payload.get("contributors") or []
    assert any(item.get("profile_id") == "cultivar.2" for item in contributors)


async def test_relink_profiles_populates_species_relationships(hass):
    species = SpeciesProfile(profile_id="species.alpha", display_name="Alpha")
    cultivar = BioProfile(
        profile_id="cultivar.beta",
        display_name="Beta",
        profile_type="cultivar",
    )
    cultivar.parents = ["species.alpha"]

    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    species_prof = reg.get("species.alpha")
    cultivar_prof = reg.get("cultivar.beta")

    assert species_prof is not None
    assert cultivar_prof is not None
    assert cultivar_prof.species_profile_id == "species.alpha"
    assert species_prof.cultivar_ids == ["cultivar.beta"]
    assert cultivar_prof.parents[0] == "species.alpha"
    assert cultivar_prof.lineage and cultivar_prof.lineage[0].profile_id == "cultivar.beta"
    assert any(entry.profile_id == "species.alpha" for entry in cultivar_prof.lineage)
    species_entry = next((entry for entry in cultivar_prof.lineage if entry.profile_id == "species.alpha"), None)
    assert species_entry is not None and species_entry.role in {"species", "parent"}


async def test_export_uses_hass_config_path(hass, tmp_path, monkeypatch):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    monkeypatch.setattr(hass, "config", type("cfg", (), {"path": lambda self, p: str(tmp_path / p)})())
    out = await reg.async_export("rel.json")
    assert out == tmp_path / "rel.json"
    assert out.exists()


async def test_replace_sensor_updates_options_without_existing_sensors(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant", "sensors": {}}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "moisture", "sensor.m")
    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["moisture"] == "sensor.m"


async def test_replace_sensor_preserves_other_profiles(hass):
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {"name": "One"},
                "p2": {"name": "Two"},
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p2", "temperature", "sensor.t")
    assert "sensors" not in entry.options[CONF_PROFILES]["p1"]


async def test_refresh_species_persists_to_store(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_refresh_species("p1")
    loaded = await profile_store.async_load_profile(hass, "p1")
    assert loaded and loaded.last_resolved == "1970-01-01T00:00:00Z"


async def test_get_returns_none_for_missing(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert reg.get("absent") is None


async def test_export_creates_parent_directories(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    nested = tmp_path / "deep" / "dir" / "profiles.json"
    await reg.async_export(nested)
    assert nested.exists()


async def test_replace_sensor_overwrites_previous_value(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "temperature", "sensor.one")
    await reg.async_replace_sensor("p1", "temperature", "sensor.two")
    sensors = entry.options[CONF_PROFILES]["p1"]["sensors"]
    assert sensors["temperature"] == "sensor.two"


async def test_export_round_trip(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    path = tmp_path / "profiles.json"
    await reg.async_export(path)
    text = path.read_text()
    data = json.loads(text)
    assert data[0]["display_name"] == "Plant"


async def test_len_after_additions(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert len(reg) == 1
    await reg.async_replace_sensor("p1", "temperature", "sensor.t")
    assert len(reg) == 1


async def test_add_profile_copy_from(hass):
    """Profiles can be created by copying an existing profile."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant", "sensors": {"temperature": "sensor.t"}}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone", base_id="p1")

    assert pid != "p1"
    sensors = entry.options[CONF_PROFILES][pid]["sensors"]
    assert sensors["temperature"] == "sensor.t"
    prof = reg.get(pid)
    assert prof.general["sensors"]["temperature"] == "sensor.t"
    assert prof.general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    sections = entry.options[CONF_PROFILES][pid]["sections"]
    assert sections["local"]["general"]["sensors"]["temperature"] == "sensor.t"


async def test_add_profile_sets_new_plant_id_in_options(hass):
    """New profiles store their own plant_id in config entry options."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"base": {"name": "Base", "plant_id": "base"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone", base_id="base")

    assert pid != "base"
    assert entry.options[CONF_PROFILES][pid]["plant_id"] == pid


async def test_add_profile_sets_plant_id_for_new_entries(hass):
    """Profiles created from scratch include plant_id metadata."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Rosemary")

    assert entry.options[CONF_PROFILES][pid]["plant_id"] == pid
    sections = entry.options[CONF_PROFILES][pid]["sections"]
    assert sections["local"]["general"].get("sensors", {}) == {}
    assert reg.get(pid).refresh_sections().local.general.get("sensors", {}) == {}


async def test_add_profile_generates_sequential_suffixes(hass):
    """New profiles receive sequentially numbered identifiers."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"tomato": {"name": "Tomato"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    first = await reg.async_add_profile("Tomato")
    assert first == "tomato_1"

    entry.options[CONF_PROFILES]["tomato_1"] = {"name": "Tomato #1"}

    second = await reg.async_add_profile("Tomato")
    assert second == "tomato_2"


async def test_add_profile_custom_scope(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("North Bay", scope="grow_zone")

    assert entry.options[CONF_PROFILES][pid][CONF_PROFILE_SCOPE] == "grow_zone"
    prof = reg.get(pid)
    assert prof is not None
    assert prof.general[CONF_PROFILE_SCOPE] == "grow_zone"


async def test_import_template_creates_profile(hass):
    """Bundled templates can seed new profiles."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_import_template("basil")

    prof = reg.get(pid)
    assert prof and prof.display_name == "Basil"
    assert prof.species == "Ocimum basilicum"


async def test_cloud_publisher_records_profile_and_events(hass, tmp_path):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    store = EdgeSyncStore(tmp_path / "sync.db")
    config = CloudSyncConfig(
        enabled=True,
        base_url="https://cloud.example",
        tenant_id="tenant-1",
        device_token="device-token",
        organization_id="org-1",
    )
    manager = SimpleNamespace(store=store, config=config)
    publisher = CloudSyncPublisher(manager, device_id="edge-1")
    reg.attach_cloud_publisher(publisher)

    profile_id = await reg.async_add_profile("Cloud Basil")
    harvest = await reg.async_record_harvest_event(
        profile_id,
        {
            "harvest_id": "harvest-1",
            "profile_id": profile_id,
            "harvested_at": "2025-01-10T00:00:00Z",
            "yield_grams": 120.5,
        },
    )

    events = store.get_outbox_batch(20)
    profile_events = [event for event in events if event.entity_type == "profile" and event.entity_id == profile_id]
    assert profile_events, "profile upsert should be queued"
    assert profile_events[-1].vector.counter == len(profile_events)

    harvest_events = [event for event in events if event.entity_type == "harvest_event"]
    assert any(event.entity_id == harvest.harvest_id for event in harvest_events)


async def test_cloud_publisher_defers_until_ready(hass, tmp_path):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    store = EdgeSyncStore(tmp_path / "sync-disabled.db")
    config = CloudSyncConfig(enabled=False)
    manager = SimpleNamespace(store=store, config=config)
    publisher = CloudSyncPublisher(manager, device_id="edge-2")
    reg.attach_cloud_publisher(publisher)

    profile_id = await reg.async_add_profile("Offline Seedling")
    assert store.outbox_size() == 0

    manager.config.enabled = True
    manager.config.base_url = "https://cloud.example"
    manager.config.tenant_id = "tenant-2"
    manager.config.device_token = "device-token"
    reg.publish_full_snapshot()

    events = store.get_outbox_batch(10)
    assert any(event.entity_type == "profile" and event.entity_id == profile_id for event in events)
