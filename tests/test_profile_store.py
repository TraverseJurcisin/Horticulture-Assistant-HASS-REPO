import pytest

from custom_components.horticulture_assistant.profile_store import (
    ProfileStore,
    StoredProfile,
)


@pytest.mark.asyncio
async def test_async_create_profile_inherits_sensors_from_existing_profile(
    hass, tmp_path, monkeypatch
) -> None:
    """Profiles cloned from storage should inherit sensor bindings."""

    monkeypatch.setattr(
        hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts))
    )
    store = ProfileStore(hass)
    await store.async_init()

    base = StoredProfile(
        name="base_profile",
        sensors={"temp": "sensor.base"},
        thresholds={"temp": {"min": 10}},
    )
    await store.async_save(base)

    await store.async_create_profile("clone_profile", clone_from="base_profile")

    clone = await store.async_get("clone_profile")
    assert clone is not None
    assert clone["sensors"] == {"temp": "sensor.base"}


@pytest.mark.asyncio
async def test_async_create_profile_clones_sensors_from_dict_payload(
    hass, tmp_path, monkeypatch
) -> None:
    """Cloning from a raw payload must copy sensor and threshold data."""

    monkeypatch.setattr(
        hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts))
    )
    store = ProfileStore(hass)
    await store.async_init()

    source_payload = {
        "sensors": {"ec": "sensor.clone"},
        "thresholds": {"ec": {"min": 1.2}},
    }

    await store.async_create_profile("payload_clone", clone_from=source_payload)

    # Mutate the source after cloning to ensure data was copied.
    source_payload["sensors"]["ec"] = "sensor.mutated"
    source_payload["thresholds"]["ec"]["min"] = 3.4

    clone = await store.async_get("payload_clone")
    assert clone is not None
    assert clone["sensors"] == {"ec": "sensor.clone"}
    assert clone["thresholds"] == {"ec": {"min": 1.2}}
