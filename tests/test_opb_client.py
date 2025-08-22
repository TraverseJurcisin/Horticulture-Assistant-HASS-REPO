import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

spec = importlib.util.spec_from_file_location(
    "opb_client",
    Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/opb_client.py",
)
opb_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(opb_module)
OpenPlantbookClient = opb_module.OpenPlantbookClient


@pytest.mark.asyncio
async def test_search_parses_results(hass):
    """OpenPlantbook search returns normalized pid/display pairs."""
    token_resp = AsyncMock()
    token_resp.__aenter__.return_value = token_resp
    token_resp.__aexit__.return_value = None
    token_resp.status = 200
    token_resp.json = AsyncMock(return_value={"access_token": "token"})

    search_resp = AsyncMock()
    search_resp.__aenter__.return_value = search_resp
    search_resp.__aexit__.return_value = None
    search_resp.status = 200
    search_resp.content_type = "application/json"
    search_resp.json = AsyncMock(
        return_value={
            "results": [
                {"pid": "pid1", "name": "Alpha"},
                {"species": "pid2", "display_name": "Beta"},
                {"name": "NoPid"},
            ]
        }
    )

    session = MagicMock()
    session.post.return_value = token_resp
    session.request.return_value = search_resp

    with patch.object(opb_module, "async_get_clientsession", return_value=session):
        client = OpenPlantbookClient(hass, "id", "secret")
        results = await client.search("query")

    assert results == [
        {"pid": "pid1", "display": "Alpha"},
        {"pid": "pid2", "display": "Beta"},
        {"pid": "NoPid", "display": "NoPid"},
    ]


@pytest.mark.asyncio
async def test_get_details_returns_json(hass):
    """Fetching species details returns the decoded payload."""

    token_resp = AsyncMock()
    token_resp.__aenter__.return_value = token_resp
    token_resp.__aexit__.return_value = None
    token_resp.status = 200
    token_resp.json = AsyncMock(return_value={"access_token": "token"})

    detail_resp = AsyncMock()
    detail_resp.__aenter__.return_value = detail_resp
    detail_resp.__aexit__.return_value = None
    detail_resp.status = 200
    detail_resp.content_type = "application/json"
    detail_resp.json = AsyncMock(return_value={"pid": "pid1", "name": "Alpha"})

    session = MagicMock()
    session.post.return_value = token_resp
    session.request.return_value = detail_resp

    with patch.object(opb_module, "async_get_clientsession", return_value=session):
        client = OpenPlantbookClient(hass, "id", "secret")
        details = await client.get_details("pid1")

    assert details == {"pid": "pid1", "name": "Alpha"}


@pytest.mark.asyncio
async def test_download_image_saves_file(tmp_path, hass):
    """Download image writes bytes and returns local path."""

    token_resp = AsyncMock()
    token_resp.__aenter__.return_value = token_resp
    token_resp.__aexit__.return_value = None
    token_resp.status = 200
    token_resp.json = AsyncMock(return_value={"access_token": "token"})

    img_resp = AsyncMock()
    img_resp.__aenter__.return_value = img_resp
    img_resp.__aexit__.return_value = None
    img_resp.status = 200
    img_resp.content_type = "image/jpeg"
    img_resp.read = AsyncMock(return_value=b"data")

    session = MagicMock()
    session.post.return_value = token_resp
    session.request.return_value = img_resp

    with patch.object(opb_module, "async_get_clientsession", return_value=session):
        client = OpenPlantbookClient(hass, "id", "secret")
        url = await client.download_image("Rose", "https://example.com/rose.jpg", tmp_path)

    assert (tmp_path / "Rose.jpg").read_bytes() == b"data"
    assert url.startswith("/local/")
