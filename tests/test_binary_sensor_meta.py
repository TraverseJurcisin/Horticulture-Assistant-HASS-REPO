import pytest
from custom_components.horticulture_assistant.binary_sensor import (
    SensorHealthBinarySensor,
)
from custom_components.horticulture_assistant.const import DOMAIN


@pytest.mark.asyncio
async def test_binary_sensor_unique_id_and_device_info(hass):
    sensor = SensorHealthBinarySensor(hass, "entry1", "Plant", "plant1", {})
    assert sensor.unique_id == f"{DOMAIN}_entry1_plant1_sensor_health"
    assert (DOMAIN, "plant:plant1") in sensor.device_info["identifiers"]
