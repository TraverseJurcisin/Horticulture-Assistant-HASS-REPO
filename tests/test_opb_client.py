import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

spec = importlib.util.spec_from_file_location(
    "opb_client",
    Path(__file__).resolve().parents[1]
    / "custom_components/horticulture_assistant/opb_client.py",
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
async def test_fetch_field_converts_to_float():
    dummy_hass = SimpleNamespace(
        helpers=SimpleNamespace(
            aiohttp_client=SimpleNamespace(async_get_clientsession=MagicMock(return_value=MagicMock()))
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
    opb_module._SPECIES_CACHE.clear()


@pytest.mark.asyncio
async def test_fetch_field_uses_cache():
    opb_module._SPECIES_CACHE.clear()
    dummy_hass = SimpleNamespace(
        helpers=SimpleNamespace(
            aiohttp_client=SimpleNamespace(async_get_clientsession=MagicMock(return_value=MagicMock()))
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
