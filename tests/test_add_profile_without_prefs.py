import importlib.util
import json
import sys
from pathlib import Path

MODULE_NAME = "custom_components.horticulture_assistant.profile_store"
MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant" / "profile_store.py"

spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = module
assert spec.loader is not None
spec.loader.exec_module(module)

ProfileStore = module.ProfileStore


async def test_create_profile_without_prefs(hass, tmp_path: Path):
    hass.config.config_dir = str(tmp_path)
    store = ProfileStore(hass)
    await store.async_init()

    await store.async_create_profile("Test Plant")
    names = await store.async_list_profiles()
    assert "Test Plant" in names

    # Verify thresholds present but empty
    profiles_dir = store._base
    profile_path = next(profiles_dir.glob("*.json"))
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    assert data["thresholds"] == {}
    assert data["resolved_targets"] == {}
