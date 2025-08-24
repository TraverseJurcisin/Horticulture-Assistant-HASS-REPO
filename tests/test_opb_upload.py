from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)


@pytest.mark.asyncio
async def test_opb_upload_with_coordinates(hass):
    hass.config.country = "US"
    hass.config.latitude = 10.0
    hass.config.longitude = 20.0
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k"},
        options={
            "sensors": {"moisture": "sensor.moisture"},
            "opb_enable_upload": True,
            "opb_credentials": {"client_id": "id", "secret": "sec"},
            "species_pid": "pid",
            "opb_location_share": "coordinates",
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.moisture", "42")

    with (
        patch("custom_components.horticulture_assistant.ChatApi"),
        patch("custom_components.horticulture_assistant.HortiAICoordinator") as mock_ai,
        patch("custom_components.horticulture_assistant.HortiLocalCoordinator") as mock_local,
        patch("custom_components.horticulture_assistant.LocalStore") as mock_store,
        patch("custom_components.horticulture_assistant.ensure_local_data_paths", AsyncMock()),
        patch("custom_components.horticulture_assistant.ensure_entities_exist"),
        patch("custom_components.horticulture_assistant.OpenPlantbookClient") as mock_client,
        patch("custom_components.horticulture_assistant.async_track_time_interval") as mock_track,
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_store.return_value.load = AsyncMock(return_value={})
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_client.return_value.upload = AsyncMock()

        await async_setup_entry(hass, entry)

        upload_cb = mock_track.call_args[0][1]
        await upload_cb(None)
        await async_unload_entry(hass, entry)

        mock_client.return_value.upload.assert_awaited_once()
        args, kwargs = mock_client.return_value.upload.call_args
        assert args[0] == entry.entry_id
        assert args[1] == "pid"
        assert args[2] == {"moisture": 42.0}
        assert kwargs["location_country"] == "US"
        assert kwargs["location_lon"] == 20.0
        assert kwargs["location_lat"] == 10.0


@pytest.mark.asyncio
async def test_opb_upload_country_only(hass):
    hass.config.country = "US"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k"},
        options={
            "sensors": {"moisture": "sensor.moisture"},
            "opb_enable_upload": True,
            "opb_credentials": {"client_id": "id", "secret": "sec"},
            "species_pid": "pid",
            "opb_location_share": "country",
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.moisture", "42")

    with (
        patch("custom_components.horticulture_assistant.ChatApi"),
        patch("custom_components.horticulture_assistant.HortiAICoordinator") as mock_ai,
        patch("custom_components.horticulture_assistant.HortiLocalCoordinator") as mock_local,
        patch("custom_components.horticulture_assistant.LocalStore") as mock_store,
        patch("custom_components.horticulture_assistant.ensure_local_data_paths", AsyncMock()),
        patch("custom_components.horticulture_assistant.ensure_entities_exist"),
        patch("custom_components.horticulture_assistant.OpenPlantbookClient") as mock_client,
        patch("custom_components.horticulture_assistant.async_track_time_interval") as mock_track,
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_store.return_value.load = AsyncMock(return_value={})
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_client.return_value.upload = AsyncMock()

        await async_setup_entry(hass, entry)

        upload_cb = mock_track.call_args[0][1]
        await upload_cb(None)
        await async_unload_entry(hass, entry)

        mock_client.return_value.upload.assert_awaited_once()
        args, kwargs = mock_client.return_value.upload.call_args
        assert args[0] == entry.entry_id
        assert args[1] == "pid"
        assert args[2] == {"moisture": 42.0}
        assert kwargs["location_country"] == "US"
        assert "location_lon" not in kwargs
        assert "location_lat" not in kwargs


@pytest.mark.asyncio
async def test_opb_upload_no_location(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k"},
        options={
            "sensors": {"moisture": "sensor.moisture"},
            "opb_enable_upload": True,
            "opb_credentials": {"client_id": "id", "secret": "sec"},
            "species_pid": "pid",
            "opb_location_share": "off",
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.moisture", "42")

    with (
        patch("custom_components.horticulture_assistant.ChatApi"),
        patch("custom_components.horticulture_assistant.HortiAICoordinator") as mock_ai,
        patch("custom_components.horticulture_assistant.HortiLocalCoordinator") as mock_local,
        patch("custom_components.horticulture_assistant.LocalStore") as mock_store,
        patch("custom_components.horticulture_assistant.ensure_local_data_paths", AsyncMock()),
        patch("custom_components.horticulture_assistant.ensure_entities_exist"),
        patch("custom_components.horticulture_assistant.OpenPlantbookClient") as mock_client,
        patch("custom_components.horticulture_assistant.async_track_time_interval") as mock_track,
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_store.return_value.load = AsyncMock(return_value={})
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_client.return_value.upload = AsyncMock()

        await async_setup_entry(hass, entry)

        upload_cb = mock_track.call_args[0][1]
        await upload_cb(None)
        await async_unload_entry(hass, entry)

        mock_client.return_value.upload.assert_awaited_once()
        args, kwargs = mock_client.return_value.upload.call_args
        assert args[0] == entry.entry_id
        assert args[1] == "pid"
        assert args[2] == {"moisture": 42.0}
        assert kwargs == {}


@pytest.mark.asyncio
async def test_opb_upload_unsub_on_unload(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k"},
        options={
            "opb_enable_upload": True,
            "opb_credentials": {"client_id": "id", "secret": "sec"},
            "species_pid": "pid",
        },
    )
    entry.add_to_hass(hass)

    remove = AsyncMock()

    with (
        patch("custom_components.horticulture_assistant.ChatApi"),
        patch("custom_components.horticulture_assistant.HortiAICoordinator") as mock_ai,
        patch("custom_components.horticulture_assistant.HortiLocalCoordinator") as mock_local,
        patch("custom_components.horticulture_assistant.LocalStore") as mock_store,
        patch("custom_components.horticulture_assistant.ensure_local_data_paths", AsyncMock()),
        patch("custom_components.horticulture_assistant.ensure_entities_exist"),
        patch("custom_components.horticulture_assistant.OpenPlantbookClient") as mock_client,
        patch(
            "custom_components.horticulture_assistant.async_track_time_interval",
            return_value=remove,
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        mock_store.return_value.load = AsyncMock(return_value={})
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_client.return_value.upload = AsyncMock()

        await async_setup_entry(hass, entry)
        await async_unload_entry(hass, entry)

        remove.assert_called_once()
