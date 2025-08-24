import types

from custom_components.horticulture_assistant.utils import (
    profile_generator,
    profile_upload_cache,
)


def _make_hass(tmp_path):
    return types.SimpleNamespace(
        config=types.SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts)))
    )


def test_generate_profile_caches(tmp_path, monkeypatch):
    hass = _make_hass(tmp_path)
    calls = []

    def fake_cache(pid, hass_arg=None):
        calls.append((pid, hass_arg))

    monkeypatch.setattr(profile_upload_cache, "cache_profile_for_upload", fake_cache)

    plant_id = profile_generator.generate_profile({"plant_name": "Mint"}, hass)

    assert plant_id == "mint"
    assert calls[0][0] == "mint"
    assert calls[0][1] is hass
