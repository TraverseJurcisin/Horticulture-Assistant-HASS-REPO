from types import SimpleNamespace

import pytest

from custom_components.horticulture_assistant import __init__ as integration


@pytest.mark.asyncio
async def test_forward_platforms_prefers_bulk_forward():
    """Use ``async_forward_entry_setups`` when available."""

    calls: list[tuple[object, tuple[str, ...]]] = []

    async def forward(entry, platforms):  # type: ignore[return-type]
        calls.append((entry, tuple(platforms)))
        return True

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=forward))
    entry = SimpleNamespace(entry_id="abc123")

    result = await integration._async_forward_entry_platforms(hass, entry)

    assert result is True
    assert calls == [(entry, tuple(integration.PLATFORMS))]


@pytest.mark.asyncio
async def test_forward_platforms_handles_sync_legacy():
    """Support synchronous legacy forwarders for test stubs."""

    calls: list[str] = []

    def forward(entry, platform):  # type: ignore[return-type]
        calls.append(platform)
        return True

    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setup=forward))
    entry = SimpleNamespace(entry_id="abc123")

    result = await integration._async_forward_entry_platforms(hass, entry)

    assert result is True
    assert set(calls) == set(integration.PLATFORMS)


@pytest.mark.asyncio
async def test_forward_platforms_missing_loader():
    """Return ``False`` when no platform forwarders are present."""

    hass = SimpleNamespace(config_entries=SimpleNamespace())
    entry = SimpleNamespace(entry_id="abc123")

    result = await integration._async_forward_entry_platforms(hass, entry)

    assert result is False
