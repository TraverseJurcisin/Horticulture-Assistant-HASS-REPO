import asyncio
from typing import Any

import pytest

from custom_components.horticulture_assistant.utils.ai_async import async_chat_completion


class DummyResponse:
    def __init__(self, *, data: dict[str, Any] | None = None, delay: float = 0.0):
        self._data = data or {"choices": [{"message": {"content": "{}"}}]}
        self.delay = delay

    async def __aenter__(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self) -> dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_chat_completion_concurrent(monkeypatch):
    import aiohttp

    calls = 0

    def fake_post(self, url, *, headers=None, json=None):
        nonlocal calls
        calls += 1
        return DummyResponse(delay=0.05)

    monkeypatch.setattr(aiohttp.ClientSession, "post", fake_post)

    msgs = [{"role": "user", "content": "hi"}]
    tasks = [async_chat_completion("k", "m", msgs) for _ in range(3)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 3
    assert calls == 3


@pytest.mark.asyncio
async def test_chat_completion_timeout(monkeypatch):
    import aiohttp

    def slow_post(self, url, *, headers=None, json=None):
        return DummyResponse(delay=0.2)

    monkeypatch.setattr(aiohttp.ClientSession, "post", slow_post)

    msgs = [{"role": "user", "content": "hi"}]
    with pytest.raises(asyncio.TimeoutError):
        await async_chat_completion("k", "m", msgs, timeout=0.05)
