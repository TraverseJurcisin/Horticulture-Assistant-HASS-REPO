import pytest
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    DOMAIN,
    signal_profile_contexts_updated,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    get_entry_data,
    profile_device_identifier,
)

dr = pytest.importorskip("homeassistant.helpers.device_registry")
er = pytest.importorskip("homeassistant.helpers.entity_registry")

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("enable_custom_integrations")]


async def test_profile_sensors_share_profile_device(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            CONF_PLANT_ID: "p1",
            CONF_PLANT_NAME: "Plant 1",
        },
        options={"thresholds": {"temperature_min": 5}},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    profile_sensor = entity_registry.async_get("sensor.plant_1_air_temperature")
    assert profile_sensor is not None
    assert profile_sensor.unique_id == f"{entry.entry_id}_p1_air_temperature"

    threshold_number = entity_registry.async_get("number.plant_1_temperature_min")
    assert threshold_number is not None
    assert threshold_number.device_id == profile_sensor.device_id

    device = device_registry.async_get(profile_sensor.device_id)
    assert device is not None
    assert profile_device_identifier(entry.entry_id, "p1") in device.identifiers


async def test_profile_sensors_migrate_unique_ids(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            CONF_PLANT_ID: "p1",
            CONF_PLANT_NAME: "Plant 1",
        },
    )
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        suggested_object_id="plant_1_air_temperature",
        unique_id=f"{entry.entry_id}_air_temperature",
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    migrated = entity_registry.async_get("sensor.plant_1_air_temperature")
    assert migrated is not None
    assert migrated.unique_id == f"{entry.entry_id}_p1_air_temperature"


async def test_added_profile_creates_sensors_and_numbers(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "k",
            CONF_PLANT_ID: "p1",
            CONF_PLANT_NAME: "Plant 1",
        },
        options={"thresholds": {}},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entry_data = get_entry_data(hass, entry)
    profile_contexts = dict(entry_data.get("profile_contexts", {}))
    profile_contexts["p2"] = {"name": "Plant 2", "thresholds": {}}
    entry_data["profile_contexts"] = profile_contexts

    async_dispatcher_send(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        {"added": ("p2",), "removed": (), "updated": ()},
    )
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    profile_sensor = entity_registry.async_get("sensor.plant_2_air_temperature")
    threshold_number = entity_registry.async_get("number.plant_2_temperature_min")

    assert profile_sensor is not None
    assert threshold_number is not None
    assert profile_sensor.device_id == threshold_number.device_id

    device = device_registry.async_get(profile_sensor.device_id)
    assert device is not None
    assert profile_device_identifier(entry.entry_id, "p2") in device.identifiers
