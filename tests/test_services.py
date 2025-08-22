import pytest
import voluptuous as vol
from unittest.mock import AsyncMock, patch
from custom_components.horticulture_assistant.const import DOMAIN, CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import issue_registry as ir, entity_registry as er

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_update_sensors_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "plant_id": "plant1", "plant_name": "Plant 1"},
        title="Plant 1",
    )
    entry.add_to_hass(hass)
    from custom_components.horticulture_assistant import async_setup_entry

    await async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"plant_id": "plant1", "sensors": {"moisture_sensors": "sensor.miss"}},
            blocking=True,
        )
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.miss"]}},
            blocking=True,
        )
    issues = ir.async_get(hass).issues
    assert any(issue_id.startswith("missing_entity") for (_, issue_id) in issues)
    hass.states.async_set("sensor.good", 1)
    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"plant_id": "plant1", "sensors": {"moisture_sensors": ["sensor.good"]}},
        blocking=True,
    )
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    assert store.data["plants"]["plant1"]["sensors"]["moisture_sensors"] == [
        "sensor.good"
    ]


async def test_replace_sensor_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "plant_id": "plant1", "plant_name": "Plant 1"},
        title="Plant 1",
        options={"sensors": {"moisture": "sensor.old"}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture"
    )
    reg.async_get_or_create(
        "sensor", "test", "sensor_good", suggested_object_id="good", original_device_class="moisture"
    )

    hass.states.async_set("sensor.old", 1)
    hass.states.async_set("sensor.good", 2)
    await hass.services.async_call(
        DOMAIN,
        "replace_sensor",
        {
            "profile_id": "plant1",
            "meter_entity": "sensor.old",
            "new_sensor": "sensor.good",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.options["sensors"]["moisture"] == "sensor.good"


async def test_refresh_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]
    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "refresh", {"bad": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert ai.async_request_refresh.called
    assert local.async_request_refresh.called


async def test_recalculate_and_run_recommendation_services(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True
        )

    store.data.setdefault("plants", {})["p1"] = {}
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    await hass.services.async_call(
        DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True
    )
    assert local.async_request_refresh.called

    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    ai.data = {"recommendation": "water"}
    await hass.services.async_call(
        DOMAIN,
        "run_recommendation",
        {"plant_id": "p1", "approve": True},
        blocking=True,
    )
    assert ai.async_request_refresh.called
    assert store.data["plants"]["p1"]["recommendation"] == "water"


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_recompute_service(hass, expected_lingering_timers):
    """Ensure recompute service validates profile id and triggers refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with patch.object(hca, "HortiAICoordinator") as mock_ai, patch.object(
        hca, "HortiLocalCoordinator"
    ) as mock_local:
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock(wraps=coord.async_request_refresh)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "recompute", {"profile_id": "bad"}, blocking=True
        )
    await hass.services.async_call(
        DOMAIN, "recompute", {"profile_id": "p1"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "recompute", {}, blocking=True)
    assert coord.async_request_refresh.call_count == 2


async def test_create_profile_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with patch.object(hca, "HortiAICoordinator") as mock_ai, patch.object(
        hca, "HortiLocalCoordinator"
    ) as mock_local:
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        DOMAIN, "create_profile", {"name": "Avocado"}, blocking=True
    )
    assert coord.async_request_refresh.called
    profiles = entry.options.get("profiles", {})
    assert any(p.get("name") == "Avocado" for p in profiles.values())


async def test_duplicate_profile_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            "profiles": {
                "p1": {
                    "name": "Plant 1",
                    "sensors": {"temperature": "sensor.temp"},
                    "thresholds": {"temp_min": 1},
                }
            }
        },
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with patch.object(hca, "HortiAICoordinator") as mock_ai, patch.object(
        hca, "HortiLocalCoordinator"
    ) as mock_local:
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        "duplicate_profile",
        {"source_profile_id": "p1", "new_name": "Copy"},
        blocking=True,
    )
    assert coord.async_request_refresh.called
    profiles = entry.options["profiles"]
    assert any(p.get("name") == "Copy" for p in profiles.values())
    new_id = next(pid for pid, p in profiles.items() if p["name"] == "Copy")
    assert profiles[new_id]["sensors"] == {"temperature": "sensor.temp"}
    assert profiles[new_id]["thresholds"] == {"temp_min": 1}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "duplicate_profile",
            {"source_profile_id": "bad", "new_name": "x"},
            blocking=True,
        )


async def test_delete_profile_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with patch.object(hca, "HortiAICoordinator") as mock_ai, patch.object(
        hca, "HortiLocalCoordinator"
    ) as mock_local:
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        DOMAIN, "delete_profile", {"profile_id": "p1"}, blocking=True
    )
    assert coord.async_request_refresh.called
    assert "p1" not in entry.options.get("profiles", {})

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "delete_profile", {"profile_id": "p1"}, blocking=True
        )


async def test_link_sensors_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with patch.object(hca, "HortiAICoordinator") as mock_ai, patch.object(
        hca, "HortiLocalCoordinator"
    ) as mock_local:
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    hass.states.async_set("sensor.temp", 10)
    await hass.services.async_call(
        DOMAIN,
        "link_sensors",
        {"profile_id": "p1", "temperature": "sensor.temp"},
        blocking=True,
    )
    assert coord.async_request_refresh.called
    assert entry.options["profiles"]["p1"]["sensors"] == {
        "temperature": "sensor.temp"
    }
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "link_sensors",
            {"profile_id": "bad", "temperature": "sensor.temp"},
            blocking=True,
        )
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "link_sensors",
            {"profile_id": "p1", "temperature": "sensor.miss"},
            blocking=True,
        )
