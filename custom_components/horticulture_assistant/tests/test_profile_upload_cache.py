import json
import types

from custom_components.horticulture_assistant.utils.profile_upload_cache import (
    cache_profile_for_upload,
)


def _make_hass(tmp_path):
    return types.SimpleNamespace(
        config=types.SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts)))
    )


def test_cache_profile_for_upload(tmp_path):
    plant_dir = tmp_path / "plants" / "demo"
    plant_dir.mkdir(parents=True)
    for name in [
        "general.json",
        "environment.json",
        "nutrition.json",
        "irrigation.json",
        "stages.json",
    ]:
        (plant_dir / name).write_text("{}")

    hass = _make_hass(tmp_path)
    cache_profile_for_upload("demo", hass)

    out = tmp_path / "data" / "profile_cache" / "demo.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "general" in data
