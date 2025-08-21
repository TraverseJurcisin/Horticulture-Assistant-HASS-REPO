import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from custom_components.horticulture_assistant.openplantbook_client import OpenPlantbookClient


class DummyApi:
    def __init__(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_search_parses_results(hass):
    """OpenPlantbook search returns normalized pid/display pairs."""
    api = DummyApi()
    api.async_plant_search = AsyncMock(
        return_value={
            "results": [
                {"pid": "pid1", "name": "Alpha"},
                {"species": "pid2", "display_name": "Beta"},
                {"name": "NoPid"},
            ]
        }
    )
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        return_value=api,
    ):
        client = OpenPlantbookClient(hass, "id", "secret")
        results = await client.search("query")

    assert results == [
        {"pid": "pid1", "display": "Alpha"},
        {"pid": "pid2", "display": "Beta"},
        {"pid": "NoPid", "display": "NoPid"},
    ]


@pytest.mark.asyncio
async def test_get_details_delegates(hass):
    """get_details returns API payload unmodified."""
    api = DummyApi()
    api.async_plant_detail_get = AsyncMock(return_value={"foo": "bar"})
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        return_value=api,
    ):
        client = OpenPlantbookClient(hass, "id", "secret")
        detail = await client.get_details("pid")

    assert detail == {"foo": "bar"}


def test_init_missing_sdk(hass):
    """Creating client without SDK raises RuntimeError."""
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        None,
    ):
        with pytest.raises(RuntimeError):
            OpenPlantbookClient(hass, "id", "secret")


@pytest.mark.asyncio
async def test_download_image_rewrites_local(hass, tmp_path):
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        DummyApi,
    ):
        client = OpenPlantbookClient(hass, "id", "secret")

    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.read.return_value = b"data"
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp

    async def run_in_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_path(*parts):
        return str(Path(tmp_path, *parts))

    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.async_get_clientsession",
        return_value=session,
    ), patch.object(hass, "async_add_executor_job", side_effect=run_in_executor), patch.object(
        hass.config, "path", side_effect=fake_path
    ):
        url = "http://example.com/path/image.png"
        dl = Path(hass.config.path("www")) / "images"
        local = await client.download_image("Test Plant", url, dl)

    assert (dl / "test_plant.png").exists()
    assert local == "/local/images/test_plant.png"


@pytest.mark.asyncio
async def test_download_image_no_www_returns_original(hass, tmp_path):
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        DummyApi,
    ):
        client = OpenPlantbookClient(hass, "id", "secret")

    resp = AsyncMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.read.return_value = b"data"
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp

    async def run_in_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_path(*parts):
        return str(Path(tmp_path, *parts))

    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.async_get_clientsession",
        return_value=session,
    ), patch.object(hass, "async_add_executor_job", side_effect=run_in_executor), patch.object(
        hass.config, "path", side_effect=fake_path
    ):
        url = "http://example.com/path/image.jpg"
        dl = tmp_path / "images"
        local = await client.download_image("Test Plant", url, dl)

    assert (dl / "test_plant.jpg").exists()
    assert local == url


@pytest.mark.asyncio
async def test_download_image_failure_returns_original(hass, tmp_path):
    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.OpenPlantBookApi",
        DummyApi,
    ):
        client = OpenPlantbookClient(hass, "id", "secret")

    session = MagicMock()
    session.get.side_effect = aiohttp.ClientError

    async def run_in_executor(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_path(*parts):
        return str(Path(tmp_path, *parts))

    with patch(
        "custom_components.horticulture_assistant.openplantbook_client.async_get_clientsession",
        return_value=session,
    ), patch.object(hass, "async_add_executor_job", side_effect=run_in_executor), patch.object(
        hass.config, "path", side_effect=fake_path
    ):
        url = "http://example.com/path/image.jpg"
        dl = Path(hass.config.path("www"))
        result = await client.download_image("Test Plant", url, dl)

    assert result == url
    assert not (dl / "test_plant.jpg").exists()
