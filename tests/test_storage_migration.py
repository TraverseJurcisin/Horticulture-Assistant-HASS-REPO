import pytest
from custom_components.horticulture_assistant.storage import migrate_v1_to_v2

pytestmark = pytest.mark.asyncio


async def test_storage_migration(tmp_path, hass):
    old = {"version": 1, "plant_registry": {"p1": {}}, "zones_registry": {}}
    new = migrate_v1_to_v2(old)
    assert new["version"] == 2
    assert "plants" in new and "zones" in new
    assert "plant_registry" not in new
