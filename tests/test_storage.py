import pytest
from custom_components.horticulture_assistant.storage import LocalStore

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

async def test_load_and_save(hass):
    store = LocalStore(hass)
    data = await store.load()
    assert "recipes" in data
    data["recipes"].append("test")
    await store.save(data)
