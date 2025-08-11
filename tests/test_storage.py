import pytest
from custom_components.horticulture_assistant.storage import LocalStore, migrate_v1_to_v2

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]

async def test_migrate_and_save(hass):
    data = {"version": 1, "profile": {}}
    migrated = migrate_v1_to_v2(data)
    assert migrated["version"] == 2
    store = LocalStore(hass)
    await store.load()
    await store.save({"profile": {}})
