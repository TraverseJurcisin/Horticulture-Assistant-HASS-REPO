import pytest

from custom_components.horticulture_assistant.coordinator_local import (
    HortiLocalCoordinator,
)
from custom_components.horticulture_assistant.storage import LocalStore

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_local_coordinator_reads_store(hass):
    store = LocalStore(hass)
    data = await store.load()
    data["recommendation"] = "hello"
    await store.save(data)
    coord = HortiLocalCoordinator(hass, store, update_minutes=1)
    result = await coord._async_update_data()
    assert result["recommendation"] == "hello"
