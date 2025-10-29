from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .utils.aiohttp import ClientError, ClientResponseError
from .utils.logging import warn_once

RETRYABLE = (429, 500, 502, 503, 504)

_LOGGER = logging.getLogger(__name__)


class ChatApi:
    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 15.0,
    ):
        self._hass = hass
        self._api_key = (api_key or "").strip()
        self._base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self._model = model or "gpt-4o"
        self._timeout = timeout
        self._failures = 0
        self._open = True  # simple circuit breaker
        self.last_latency_ms: int | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 256,
    ) -> dict[str, Any]:
        if not self._open:
            raise RuntimeError("Circuit open; skipping call")
        session = aiohttp_client.async_get_clientsession(self._hass)
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = f"{self._base_url}/chat/completions"

        delay = 1.0
        for attempt in range(5):
            try:
                async with asyncio.timeout(self._timeout):
                    t0 = time.perf_counter()
                    async with session.post(url, headers=self._headers(), json=payload) as resp:
                        if resp.status in {401, 403}:
                            resp.raise_for_status()
                        if resp.status in RETRYABLE:
                            raise ClientError(f"Retryable status: {resp.status}")
                        resp.raise_for_status()
                        self._failures = 0
                        self._open = True
                        data = await resp.json()
                        self.last_latency_ms = int((time.perf_counter() - t0) * 1000)
                        return data
            except ClientResponseError as err:
                self._failures += 1
                if err.status in {401, 403}:
                    self._trip_circuit()
                    raise
                warn_once(_LOGGER, f"http_{err.status}", f"API error {err.status}")
                if attempt == 4:
                    self._trip_circuit()
                    raise
                await asyncio.sleep(delay + 0.25 * random.random())
                delay = min(delay * 2, 30)
            except (TimeoutError, ClientError) as err:
                self._failures += 1
                warn_once(_LOGGER, "network_error", str(err))
                if attempt == 4:
                    self._trip_circuit()
                    raise
                await asyncio.sleep(delay + 0.25 * random.random())
                delay = min(delay * 2, 30)

        raise RuntimeError("Failed to fetch chat completion")

    def _half_open(self) -> None:
        self._open = True

    def _trip_circuit(self) -> None:
        self._open = False
        loop = getattr(self._hass, "loop", None)
        if loop is None:
            return
        try:
            loop.call_later(60, self._half_open)
        except Exception:  # pragma: no cover - defensive guard
            _LOGGER.debug("Failed to schedule circuit half-open transition", exc_info=True)

    async def validate_api_key(self) -> None:
        """Simple call to validate API key."""
        await self.chat(
            [
                {"role": "user", "content": "ping"},
            ],
            max_tokens=1,
        )
