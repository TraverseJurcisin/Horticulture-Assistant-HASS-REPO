import importlib
import logging
import pathlib
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import MockConfigEntry

# Bypass the package __init__ which pulls in Home Assistant by creating a minimal
# module placeholder with an explicit path for submodule resolution.
pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

const = importlib.import_module("custom_components.horticulture_assistant.const")
coordinator_mod = importlib.import_module("custom_components.horticulture_assistant.coordinator")
entity_mod = importlib.import_module("custom_components.horticulture_assistant.entity")
sensor_mod = importlib.import_module("custom_components.horticulture_assistant.sensor")
schema_mod = importlib.import_module("custom_components.horticulture_assistant.profile.schema")
metrics_mod = importlib.import_module("custom_components.horticulture_assistant.engine.metrics")

CONF_PROFILES = const.CONF_PROFILES
CONF_CLOUD_SYNC_ENABLED = const.CONF_CLOUD_SYNC_ENABLED
CONF_CLOUD_ACCOUNT_EMAIL = const.CONF_CLOUD_ACCOUNT_EMAIL
CONF_CLOUD_ACCOUNT_ROLES = const.CONF_CLOUD_ACCOUNT_ROLES
DOMAIN = const.DOMAIN
FEATURE_CLOUD_SYNC = const.FEATURE_CLOUD_SYNC
FEATURE_AI_ASSIST = const.FEATURE_AI_ASSIST
FEATURE_IRRIGATION_AUTOMATION = const.FEATURE_IRRIGATION_AUTOMATION
HorticultureCoordinator = coordinator_mod.HorticultureCoordinator
HorticultureEntity = entity_mod.HorticultureEntity
ProfileMetricSensor = sensor_mod.ProfileMetricSensor
PROFILE_SENSOR_DESCRIPTIONS = sensor_mod.PROFILE_SENSOR_DESCRIPTIONS
GardenSummarySensor = sensor_mod.GardenSummarySensor
EntitlementSummarySensor = sensor_mod.EntitlementSummarySensor
ProfileSuccessSensor = sensor_mod.ProfileSuccessSensor
ProfileProvenanceSensor = sensor_mod.ProfileProvenanceSensor
ProfileFeedingSensor = sensor_mod.ProfileFeedingSensor
ProfileYieldSensor = sensor_mod.ProfileYieldSensor
ProfileEventSensor = sensor_mod.ProfileEventSensor
BioProfile = schema_mod.BioProfile
ComputedStatSnapshot = schema_mod.ComputedStatSnapshot
ProfileContribution = schema_mod.ProfileContribution
FieldAnnotation = schema_mod.FieldAnnotation
ResolvedTarget = schema_mod.ResolvedTarget
vpd_kpa = metrics_mod.vpd_kpa


def _make_entry(*, options=None, data=None, entry_id="entry1") -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=data or {}, options=options or {})
    entry.entry_id = entry_id
    return entry


@pytest.mark.asyncio
async def test_coordinator_returns_profile_data(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    assert "profiles" in coordinator.data
    assert "avocado" in coordinator.data["profiles"]
    prof = coordinator.data["profiles"]["avocado"]
    assert prof["name"] == "Avocado"
    assert prof["metrics"]["dli"] is None
    assert "mold_risk" in prof["metrics"]


@pytest.mark.asyncio
async def test_coordinator_honors_update_interval(hass):
    options = {CONF_PROFILES: {}, "update_interval": 10}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    assert coordinator.update_interval.total_seconds() == 600


@pytest.mark.asyncio
async def test_base_entity_device_info(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    entity = HorticultureEntity(coordinator, "avocado", "Avocado")
    info = entity.device_info
    assert info["name"] == "Avocado"
    assert info["identifiers"] == {("horticulture_assistant", "profile:avocado")}


@pytest.mark.asyncio
async def test_dli_sensor_reads_illuminance(hass):
    hass.states.async_set("sensor.light", 2000)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"illuminance": "sensor.light"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    ppfd_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["ppfd"])
    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    # 2000 lux -> 37 PPFD; over a 5-minute interval yields ~0.011 mol/m²·day
    assert ppfd_sensor.native_value == pytest.approx(37.0, rel=1e-2)
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)


@pytest.mark.asyncio
async def test_dli_accumulates_over_updates(hass):
    hass.states.async_set("sensor.light", 2000)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"illuminance": "sensor.light"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_request_refresh()

    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    assert dli_sensor.native_value == pytest.approx(0.022, rel=1e-2)


@pytest.mark.asyncio
async def test_dli_resets_daily(hass):
    hass.states.async_set("sensor.light", 2000)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"illuminance": "sensor.light"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start,
    ):
        await coordinator.async_config_entry_first_refresh()
    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start + timedelta(days=1),
    ):
        await coordinator.async_request_refresh()
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)


@pytest.mark.asyncio
async def test_profile_vpd_and_dew_point_sensors(hass):
    hass.states.async_set("sensor.t", 25)
    hass.states.async_set("sensor.h", 60)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"temperature": "sensor.t", "humidity": "sensor.h"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    vpd_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["vpd"])
    dew_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dew_point"])
    vpd_avg_sensor = ProfileMetricSensor(
        coordinator,
        "avocado",
        "Avocado",
        PROFILE_SENSOR_DESCRIPTIONS["vpd_7d_avg"],
    )
    assert vpd_sensor.native_value == pytest.approx(1.27, rel=1e-2)
    assert dew_sensor.native_value == pytest.approx(16.7, rel=1e-2)
    assert vpd_avg_sensor.native_value == pytest.approx(1.27, rel=1e-2)
    assert coordinator.data["profiles"]["avocado"]["metrics"]["mold_risk"] == 0.0


@pytest.mark.asyncio
async def test_vpd_seven_day_average_rollover(hass):
    hass.states.async_set("sensor.t", 25)
    hass.states.async_set("sensor.h", 60)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"temperature": "sensor.t", "humidity": "sensor.h"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    start = datetime(2024, 4, 1, tzinfo=dt_util.UTC)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start,
    ):
        await coordinator.async_config_entry_first_refresh()
    avg_sensor = ProfileMetricSensor(
        coordinator,
        "avocado",
        "Avocado",
        PROFILE_SENSOR_DESCRIPTIONS["vpd_7d_avg"],
    )
    first_vpd = vpd_kpa(25, 60)
    assert avg_sensor.native_value == pytest.approx(first_vpd, rel=1e-2)

    hass.states.async_set("sensor.h", 40)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start + timedelta(days=3),
    ):
        await coordinator.async_request_refresh()
    second_vpd = vpd_kpa(25, 40)
    assert avg_sensor.native_value == pytest.approx((first_vpd + second_vpd) / 2, rel=1e-2)

    hass.states.async_set("sensor.h", 50)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start + timedelta(days=8),
    ):
        await coordinator.async_request_refresh()
    third_vpd = vpd_kpa(25, 50)
    assert avg_sensor.native_value == pytest.approx(third_vpd, rel=1e-2)


@pytest.mark.asyncio
async def test_profile_moisture_sensor(hass):
    hass.states.async_set("sensor.m", 55)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"moisture": "sensor.m"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    moisture_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["moisture"])
    assert moisture_sensor.native_value == 55


@pytest.mark.asyncio
async def test_profile_status_sensor(hass):
    hass.states.async_set("sensor.m", 5)
    hass.states.async_set("sensor.t", 25)
    hass.states.async_set("sensor.h", 95)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {
                    "moisture": "sensor.m",
                    "temperature": "sensor.t",
                    "humidity": "sensor.h",
                },
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()
    status_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["status"])
    assert status_sensor.native_value == "critical"


@pytest.mark.asyncio
async def test_garden_summary_sensor_reports_problem_count(hass):
    hass.states.async_set("sensor.m1", 5)
    hass.states.async_set("sensor.t1", 25)
    hass.states.async_set("sensor.h1", 95)
    hass.states.async_set("sensor.m2", 55)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {
                    "moisture": "sensor.m1",
                    "temperature": "sensor.t1",
                    "humidity": "sensor.h1",
                },
            },
            "basil": {
                "name": "Basil",
                "sensors": {
                    "moisture": "sensor.m2",
                },
            },
        }
    }
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()
    summary_sensor = GardenSummarySensor(coordinator, "entry1", "Garden")
    assert summary_sensor.native_value == 1
    attrs = summary_sensor.extra_state_attributes
    assert attrs["total_profiles"] == 2
    assert attrs["problem_profiles"] == 1
    assert attrs["status_critical"] == 1
    assert attrs.get("status_ok", 0) >= 1


@pytest.mark.asyncio
async def test_entitlement_sensor_exposes_features(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_ACCOUNT_EMAIL: "grower@example.com",
            CONF_CLOUD_ACCOUNT_ROLES: ["premium"],
        },
    )
    sensor = EntitlementSummarySensor(entry)
    sensor.hass = hass
    await sensor.async_update()
    assert sensor.native_value == "premium"
    attrs = sensor.extra_state_attributes
    assert FEATURE_CLOUD_SYNC in attrs["features"]
    assert FEATURE_AI_ASSIST in attrs["features"]
    assert FEATURE_IRRIGATION_AUTOMATION in attrs["features"]
    assert attrs["account_email"] == "grower@example.com"


@pytest.mark.asyncio
async def test_status_and_recommendation_device_info(hass):
    async def _async_update():
        return {}

    ai = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="ai", update_method=_async_update)
    local = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="local", update_method=_async_update)
    status = sensor_mod.HortiStatusSensor(ai, local, "entry1", "Plant", "pid", True)
    rec = sensor_mod.HortiRecommendationSensor(ai, "entry1", "Plant", "pid", True)
    info = status.device_info
    assert info["identifiers"] == {("horticulture_assistant", "plant:pid")}
    assert info["name"] == "Plant"
    assert rec.device_info == info


@pytest.mark.asyncio
async def test_profile_success_sensor_uses_latest_snapshot(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    profile = BioProfile(profile_id="avocado", display_name="Avocado")
    snapshot = ComputedStatSnapshot(
        stats_version="success/v1",
        computed_at="2025-05-01T12:00:00Z",
        payload={
            "weighted_success_percent": 92.5,
            "average_success_percent": 91.0,
            "samples_recorded": 3,
            "runs_tracked": 2,
            "targets_met": 80.0,
            "targets_total": 100.0,
            "stress_events": 2,
            "best_success_percent": 95.0,
            "worst_success_percent": 90.0,
            "contributors": [
                {
                    "profile_id": "avocado",
                    "samples_recorded": 3,
                    "weighted_success_percent": 92.5,
                }
            ],
        },
        contributions=[
            ProfileContribution(
                profile_id="avocado",
                child_id="avocado",
                stats_version="success/v1",
                weight=1.0,
                n_runs=2,
            )
        ],
    )
    profile.computed_stats.append(snapshot)

    class DummyRegistry:
        def __init__(self, prof):
            self._profile = prof

        def get_profile(self, profile_id):
            if profile_id == self._profile.profile_id:
                return self._profile
            return None

    sensor = ProfileSuccessSensor(coordinator, DummyRegistry(profile), "avocado", "Avocado")
    assert sensor.native_value == pytest.approx(92.5)
    attrs = sensor.extra_state_attributes
    assert attrs["samples_recorded"] == 3
    assert attrs["targets_met"] == pytest.approx(80.0)
    assert attrs["targets_total"] == pytest.approx(100.0)
    assert attrs["stress_events"] == 2
    assert attrs["best_success_percent"] == pytest.approx(95.0)
    assert attrs["worst_success_percent"] == pytest.approx(90.0)
    assert attrs["contributors"][0]["profile_id"] == "avocado"


@pytest.mark.asyncio
async def test_profile_provenance_sensor_summarises_sources(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    profile = BioProfile(profile_id="avocado", display_name="Avocado")
    profile.resolved_targets["humidity_optimal"] = ResolvedTarget(
        value=60,
        annotation=FieldAnnotation(source_type="manual", method="manual"),
        citations=[],
    )
    profile.resolved_targets["temperature_optimal"] = ResolvedTarget(
        value=21.5,
        annotation=FieldAnnotation(
            source_type="inheritance",
            source_ref=["avocado", "species"],
            method="inheritance",
            extras={"inheritance_depth": 1, "source_profile_id": "species"},
        ),
        citations=[],
    )
    profile.refresh_sections()

    class DummyRegistry:
        def __init__(self, prof):
            self._profile = prof

        def get_profile(self, profile_id):
            if profile_id == self._profile.profile_id:
                return self._profile
            return None

    sensor = ProfileProvenanceSensor(coordinator, DummyRegistry(profile), "avocado", "Avocado")
    assert sensor.native_value == 1
    attrs = sensor.extra_state_attributes
    assert attrs["inherited_count"] == 1
    assert attrs["override_count"] == 1
    assert attrs["total_targets"] == 2
    assert "temperature_optimal" in attrs["inherited_fields"]
    assert attrs["provenance_map"]["humidity_optimal"]["source_type"] == "manual"
    assert attrs["badges"]["temperature_optimal"]["badge"] == "inherited"
    assert attrs["badge_counts"]["override"] == 1


@pytest.mark.asyncio
async def test_profile_yield_sensor_reports_totals(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    profile = BioProfile(profile_id="avocado", display_name="Avocado")
    snapshot = ComputedStatSnapshot(
        stats_version="yield/v1",
        computed_at="2024-05-01T00:00:00Z",
        snapshot_id="avocado:yield/v1",
        payload={
            "scope": "cultivar",
            "metrics": {
                "total_yield_grams": 120.5,
                "harvest_count": 3,
                "average_yield_grams": 40.166,
                "average_yield_density_g_m2": 30.125,
                "days_since_last_harvest": 4.5,
                "total_fruit_count": 15.0,
            },
            "yields": {"total_grams": 120.5, "total_area_m2": 4.0, "total_fruit_count": 15},
            "densities": {"average_g_m2": 30.125},
            "runs_tracked": 2,
            "window_totals": {
                "7d": {"harvest_count": 1.0, "total_yield_grams": 40.0},
                "30d": {
                    "harvest_count": 3.0,
                    "total_yield_grams": 120.5,
                    "fruit_count": 15.0,
                },
            },
            "last_harvest_at": "2024-04-27T09:00:00+00:00",
            "days_since_last_harvest": 4.5,
        },
        contributions=[],
    )
    profile.computed_stats.append(snapshot)

    class DummyRegistry:
        def __init__(self, prof):
            self._profile = prof

        def get_profile(self, profile_id):
            if profile_id == self._profile.profile_id:
                return self._profile
            return None

    sensor = ProfileYieldSensor(coordinator, DummyRegistry(profile), "avocado", "Avocado")
    assert sensor.native_value == pytest.approx(120.5, rel=1e-3)
    attrs = sensor.extra_state_attributes
    assert attrs["harvest_count"] == 3
    assert attrs["total_grams"] == 120.5
    assert attrs["density_average_g_m2"] == 30.125
    assert attrs["total_kilograms"] == pytest.approx(0.1205, rel=1e-3)
    assert attrs["average_yield_kilograms"] == pytest.approx(0.040, rel=1e-2)
    assert attrs["average_yield_density_kg_m2"] == pytest.approx(0.030, rel=1e-2)
    assert attrs["density_average_kg_m2"] == pytest.approx(0.030, rel=1e-2)
    assert attrs["total_fruit_count"] == 15
    assert attrs["days_since_last_harvest"] == 4.5
    assert attrs["window_totals"]["30d"]["harvest_count"] == 3.0


@pytest.mark.asyncio
async def test_profile_event_sensor_summarises_activity(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    profile = BioProfile(profile_id="avocado", display_name="Avocado")
    snapshot = ComputedStatSnapshot(
        stats_version="events/v1",
        computed_at="2024-05-02T12:00:00Z",
        snapshot_id="avocado:events/v1",
        payload={
            "scope": "cultivar",
            "metrics": {
                "total_events": 2.0,
                "unique_event_types": 2.0,
                "days_since_last_event": 1.5,
            },
            "last_event": {"event_type": "inspection", "notes": "All good"},
            "event_types": [{"event_type": "inspection", "count": 1}],
            "top_tags": [{"tag": "health", "count": 1}],
            "window_counts": {"7d": 1, "30d": 2},
        },
        contributions=[],
    )
    profile.computed_stats.append(snapshot)

    class DummyRegistry:
        def __init__(self, prof):
            self._profile = prof

        def get_profile(self, profile_id):
            if profile_id == self._profile.profile_id:
                return self._profile
            return None

    sensor = ProfileEventSensor(coordinator, DummyRegistry(profile), "avocado", "Avocado")
    assert sensor.native_value == 2
    attrs = sensor.extra_state_attributes
    assert attrs["unique_event_types"] == 2.0
    assert attrs["last_event"]["event_type"] == "inspection"
    assert attrs["top_tags"][0]["tag"] == "health"
    assert attrs["window_counts"]["7d"] == 1


@pytest.mark.asyncio
async def test_profile_feeding_sensor_summarises_events(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, _make_entry(options=options))
    await coordinator.async_config_entry_first_refresh()

    profile = BioProfile(profile_id="avocado", display_name="Avocado")
    snapshot = ComputedStatSnapshot(
        stats_version=sensor_mod.NUTRIENT_STATS_VERSION,
        computed_at="2024-03-05T10:00:00Z",
        snapshot_id="avocado:nutrients/v1",
        payload={
            "scope": "cultivar",
            "metrics": {"total_events": 2.0, "days_since_last_event": 4.5},
            "last_event": {"product_name": "Grow A", "solution_volume_liters": 9.5},
            "product_usage": [{"product": "Grow A", "count": 2}],
            "window_counts": {"7d": 1, "30d": 2},
        },
    )
    profile.computed_stats.append(snapshot)

    class DummyRegistry:
        def __init__(self, prof):
            self._profile = prof

        def get_profile(self, profile_id):
            if profile_id == self._profile.profile_id:
                return self._profile
            return None

    sensor = ProfileFeedingSensor(coordinator, DummyRegistry(profile), "avocado", "Avocado")
    assert sensor.native_value == pytest.approx(4.5)
    attrs = sensor.extra_state_attributes
    assert attrs["metrics"]["total_events"] == 2.0
    assert attrs["last_event"]["product_name"] == "Grow A"
    assert attrs["window_counts"]["7d"] == 1
