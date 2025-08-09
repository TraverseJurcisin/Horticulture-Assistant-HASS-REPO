import pytest
from custom_components.horticulture_assistant.coordinator import HortiCoordinator
from custom_components.horticulture_assistant.storage import LocalStore

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

class DummyApi:
    def __init__(self, fail=False):
        self.fail = fail

    async def chat(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("boom")
        return {"choices": [{"message": {"content": "hi"}}]}

async def test_coordinator_success(hass):
    store = LocalStore(hass)
    await store.load()
    coord = HortiCoordinator(hass, DummyApi(), store, update_minutes=5)
    data = await coord._async_update_data()
    assert data["ok"]

async def test_coordinator_failure(hass):
    store = LocalStore(hass)
    await store.load()
    coord = HortiCoordinator(hass, DummyApi(fail=True), store, update_minutes=5)
    with pytest.raises(Exception):
        await coord._async_update_data()
    assert coord.retry_count == 1
