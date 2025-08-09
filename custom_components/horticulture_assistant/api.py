from __future__ import annotations
import asyncio
import math
import time
from typing import Any
from aiohttp import ClientError
from homeassistant.core import HomeAssistant

RETRYABLE = (429, 500, 502, 503, 504)

class ChatApi:
    def __init__(self, hass: HomeAssistant, api_key: str, base_url: str, model: str, timeout: float = 15.0):
        self._hass = hass
        self._api_key = (api_key or "").strip()
        self._base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self._model = model or "gpt-4o"
        self._timeout = timeout
        self._failures = 0
        self._open = True  # simple circuit breaker

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    async def chat(self, messages: list[dict[str, Any]], temperature: float = 0.2, max_tokens: int = 256) -> dict[str, Any]:
        if not self._open:
            raise RuntimeError("Circuit open; skipping call")
        session = self._hass.helpers.aiohttp_client.async_get_clientsession()
        payload = {"model": self._model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        url = f"{self._base_url}/chat/completions"

        delay = 1.0
        for attempt in range(5):
            try:
                async with asyncio.timeout(self._timeout):
                    async with session.post(url, headers=self._headers(), json=payload) as resp:
                        if resp.status in RETRYABLE:
                            raise ClientError(f"Retryable status: {resp.status}")
                        resp.raise_for_status()
                        self._failures = 0
                        self._open = True
                        return await resp.json()
            except (ClientError, asyncio.TimeoutError):
                self._failures += 1
                if attempt == 4:
                    self._open = False
                    # auto half-open after 60s
                    self._hass.loop.call_later(60, self._half_open)
                    raise
                # exp backoff + small jitter
                await asyncio.sleep(delay + 0.25 * (0.5 - math.sin(time.time())))
                delay = min(delay * 2, 30)

        raise RuntimeError("Failed to fetch chat completion")

    def _half_open(self) -> None:
        self._open = True
