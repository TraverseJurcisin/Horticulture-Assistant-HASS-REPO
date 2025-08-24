import asyncio
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

spec = importlib.util.spec_from_file_location(
    "opb_client",
    Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/opb_client.py",
)
opb_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(opb_module)
OpenPlantbookClient = opb_module.OpenPlantbookClient
async_fetch_field = opb_module.async_fetch_field


@pytest.mark.asyncio
async def test_species_details_returns_json():
    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.status = 200
    resp.json = AsyncMock(return_value={"ok": True})
    session = MagicMock()
    session.get.return_value = resp
    client = OpenPlantbookClient(session, "token")
    data = await client.species_details("slug")
    assert data == {"ok": True}
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_search_returns_list():
    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.status = 200
    resp.json = AsyncMock(return_value=[{"pid": "p"}])
    session = MagicMock()
    session.get.return_value = resp
    client = OpenPlantbookClient(session, "token")
    data = await client.search("q")
    assert data == [{"pid": "p"}]
    session.get.assert_called_once()


@pytest.mark.asyncio
async def test_request_errors_are_wrapped():
    session = MagicMock()
    session.get.side_effect = aiohttp.ClientError("boom")
    client = OpenPlantbookClient(session, None)
    with pytest.raises(opb_module.OpenPlantbookError):
        await client.species_details("slug")


@pytest.mark.asyncio
async def test_request_timeout_is_wrapped():
    session = MagicMock()
    session.get.side_effect = asyncio.TimeoutError
    client = OpenPlantbookClient(session, None)
    with pytest.raises(opb_module.OpenPlantbookError):
        await client.species_details("slug")


@pytest.mark.asyncio
async def test_request_non_200():
    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.status = 404
    resp.json = AsyncMock(return_value={})
    session = MagicMock()
    session.get.return_value = resp
    client = OpenPlantbookClient(session, None)
    with pytest.raises(opb_module.OpenPlantbookError):
        await client.species_details("slug")


@pytest.mark.asyncio
async def test_request_invalid_json():
    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.status = 200
    resp.json = AsyncMock(side_effect=aiohttp.ContentTypeError(None, ()))
    session = MagicMock()
    session.get.return_value = resp
    client = OpenPlantbookClient(session, None)
    with pytest.raises(opb_module.OpenPlantbookError):
        await client.species_details("slug")


@pytest.mark.asyncio
async def test_fetch_field_converts_to_float():
    dummy_hass = SimpleNamespace(
        helpers=SimpleNamespace(
            aiohttp_client=SimpleNamespace(
                async_get_clientsession=MagicMock(return_value=MagicMock())
            )
        )
    )
    with patch.object(
        opb_module.OpenPlantbookClient,
        "species_details",
        AsyncMock(return_value={"temp": {"min_c": "21"}}),
    ):
        val, url = await async_fetch_field(dummy_hass, "slug", "temp.min_c")
    assert val == 21.0
    assert url == "https://openplantbook.org/slug"
    opb_module.clear_opb_cache()


@pytest.mark.asyncio
async def test_fetch_field_uses_cache():
    opb_module.clear_opb_cache()
    dummy_hass = SimpleNamespace(
        helpers=SimpleNamespace(
            aiohttp_client=SimpleNamespace(
                async_get_clientsession=MagicMock(return_value=MagicMock())
            )
        )
    )
    with patch.object(
        opb_module.OpenPlantbookClient,
        "species_details",
        AsyncMock(side_effect=[{"temp": {"min_c": "21"}}, {"temp": {"min_c": "18"}}]),
    ) as mock_details:
        val1, _ = await async_fetch_field(dummy_hass, "slug", "temp.min_c")
        val2, _ = await async_fetch_field(dummy_hass, "slug", "temp.min_c")
    assert val1 == 21.0
    assert val2 == 21.0
    mock_details.assert_called_once()


@pytest.mark.asyncio
async def test_search_uses_cache():
    opb_module.clear_opb_cache()
    session = MagicMock()
    client = OpenPlantbookClient(session, None)
    with patch.object(
        OpenPlantbookClient, "_get", AsyncMock(return_value=[{"pid": "p"}])
    ) as mock_get:
        data1 = await client.search("foo")
        data2 = await client.search("foo")
    assert data1 == data2 == [{"pid": "p"}]
    mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_field_cache_expires():
    opb_module.clear_opb_cache()
    dummy_hass = SimpleNamespace(
        helpers=SimpleNamespace(
            aiohttp_client=SimpleNamespace(
                async_get_clientsession=MagicMock(return_value=MagicMock())
            )
        )
    )
    now = datetime(2024, 1, 1, tzinfo=UTC)
    with (
        patch.object(opb_module, "_CACHE_TTL", timedelta(seconds=1)),
        patch.object(opb_module, "datetime") as dt,
        patch.object(
            opb_module.OpenPlantbookClient,
            "species_details",
            AsyncMock(side_effect=[{"temp": {"min_c": "21"}}, {"temp": {"min_c": "22"}}]),
        ) as mock_details,
    ):
        dt.now.side_effect = [now, now + timedelta(seconds=2)]
        val1, _ = await async_fetch_field(dummy_hass, "slug", "temp.min_c")
        val2, _ = await async_fetch_field(dummy_hass, "slug", "temp.min_c")
    assert val1 == 21.0
    assert val2 == 22.0
    assert mock_details.call_count == 2


@pytest.mark.asyncio
async def test_search_cache_expires():
    opb_module.clear_opb_cache()
    session = MagicMock()
    client = OpenPlantbookClient(session, None)
    now = datetime(2024, 1, 1, tzinfo=UTC)
    with (
        patch.object(opb_module, "_CACHE_TTL", timedelta(seconds=1)),
        patch.object(opb_module, "datetime") as dt,
        patch.object(
            OpenPlantbookClient, "_get", AsyncMock(side_effect=[[{"pid": "p1"}], [{"pid": "p2"}]])
        ) as mock_get,
    ):
        dt.now.side_effect = [now, now + timedelta(seconds=2)]
        data1 = await client.search("foo")
        data2 = await client.search("foo")
    assert data1 == [{"pid": "p1"}]
    assert data2 == [{"pid": "p2"}]
    assert mock_get.call_count == 2
