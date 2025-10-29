"""Tests for the :mod:`custom_components.horticulture_assistant.api` module."""

from __future__ import annotations

import asyncio
import types
from collections.abc import Callable
from typing import Any

import pytest

from custom_components.horticulture_assistant import api as api_module


class DummyResponse:
    """Simple async context manager emulating an aiohttp response."""

    status = 200

    def __init__(self, session: DummySession) -> None:
        self._session = session

    async def __aenter__(self) -> DummyResponse:
        self._session.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def json(self) -> dict[str, bool]:
        return {"ok": True}

    def raise_for_status(self) -> None:  # pragma: no cover - happy path
        return None


class DummySession:
    """Capture the payload sent to the HTTP client."""

    def __init__(
        self,
        response_factory: Callable[[DummySession], DummyResponse] | type[DummyResponse] = DummyResponse,
    ) -> None:
        self.post_called = 0
        self.kwargs: dict[str, object] | None = None
        self.entered = False
        self._factory = response_factory

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> DummyResponse:
        self.post_called += 1
        self.kwargs = {"url": url, "headers": headers, "json": json}
        factory = self._factory
        if isinstance(factory, type):
            return factory(self)
        return factory(self)


class UnauthorizedResponse(DummyResponse):
    """Response that simulates a 401 from the API."""

    status = 401

    def raise_for_status(self) -> None:  # pragma: no cover - exercised in tests
        raise api_module.ClientResponseError(
            request_info=types.SimpleNamespace(real_url="https://example.com/api/chat/completions"),
            history=(),
            status=401,
            message="Unauthorized",
        )


class FakeLoop:
    """Collect callbacks scheduled via ``call_later`` for inspection."""

    def __init__(self) -> None:
        self.scheduled: list[tuple[float, Callable[..., None], tuple[Any, ...]]] = []

    def call_later(self, delay: float, callback, *args):  # type: ignore[override]
        self.scheduled.append((delay, callback, args))
        return types.SimpleNamespace(cancel=lambda: None)


@pytest.mark.asyncio
async def test_chat_api_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """The chat API should call the HTTP client and return the payload."""

    session = DummySession()
    monkeypatch.setattr(
        api_module.aiohttp_client,
        "async_get_clientsession",
        lambda hass: session,
    )

    hass = types.SimpleNamespace(loop=asyncio.get_running_loop())
    api = api_module.ChatApi(hass, "token", "https://example.com/api", "gpt-test")

    result = await api.chat([{"role": "user", "content": "hi"}], temperature=0.3, max_tokens=42)

    assert session.post_called == 1
    assert session.entered is True
    assert session.kwargs is not None
    assert session.kwargs["url"] == "https://example.com/api/chat/completions"
    assert result == {"ok": True}
    assert isinstance(api.last_latency_ms, int)


@pytest.mark.asyncio
async def test_chat_api_unauthorized_trips_circuit_temporarily(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unauthorized responses should trip the circuit but recover automatically."""

    session = DummySession(UnauthorizedResponse)
    loop = FakeLoop()
    hass = types.SimpleNamespace(loop=loop)

    monkeypatch.setattr(
        api_module.aiohttp_client,
        "async_get_clientsession",
        lambda hass: session,
    )

    api = api_module.ChatApi(hass, "bad", "https://example.com/api", "gpt-test")

    with pytest.raises(api_module.ClientResponseError):
        await api.chat([{"role": "user", "content": "hi"}])

    assert session.post_called == 1
    assert session.entered is True
    assert loop.scheduled
    delay, callback, args = loop.scheduled[0]
    assert delay == pytest.approx(60.0)
    assert api._open is False

    callback(*args)

    assert api._open is True
