import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
