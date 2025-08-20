import pytest
from pathlib import Path
from custom_components.horticulture_assistant.storage import LocalStore, DEFAULT_DATA

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


async def test_load_corrupt_file_returns_default(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    storage_dir = Path(tmp_path) / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "horticulture_assistant.data").write_text("not json")

    store = LocalStore(hass)
    data = await store.load()
    assert data == DEFAULT_DATA
