import pytest
from aiohttp import ClientError
from unittest.mock import AsyncMock

from custom_components.horticulture_assistant.api import ChatApi


class DummyResp:
    def __init__(self, status, data=None, headers=None):
        self.status = status
        self._data = data or {}
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise ClientError(f"status {self.status}")

    async def json(self):
        return self._data


@pytest.mark.asyncio
async def test_retry_success(hass, monkeypatch):
    api = ChatApi(hass, "key", None, "model", max_retries=2, initial_delay=0)

    responses = [DummyResp(500), DummyResp(200, {"ok": True})]

    class Session:
        def __init__(self):
            self.calls = 0

        def post(self, url, headers=None, json=None):
            self.calls += 1
            return responses.pop(0)

    session = Session()
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.api.aiohttp_client.async_get_clientsession",
        lambda hass: session,
    )

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr("custom_components.horticulture_assistant.api.asyncio.sleep", fake_sleep)

    result = await api.chat([{"role": "user", "content": "hi"}])
    assert result == {"ok": True}
    assert session.calls == 2
    assert len(sleep_calls) == 1


@pytest.mark.asyncio
async def test_retry_exhaustion(hass, monkeypatch):
    api = ChatApi(hass, "key", None, "model", max_retries=1, initial_delay=0)

    class Session:
        def __init__(self):
            self.calls = 0

        def post(self, url, headers=None, json=None):
            self.calls += 1
            return DummyResp(500)

    session = Session()
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.api.aiohttp_client.async_get_clientsession",
        lambda hass: session,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.api.asyncio.sleep", AsyncMock()
    )
    monkeypatch.setattr(hass.loop, "call_later", lambda *args, **kwargs: None)

    with pytest.raises(ClientError):
        await api.chat([{"role": "user", "content": "hi"}])
    assert session.calls == 2
