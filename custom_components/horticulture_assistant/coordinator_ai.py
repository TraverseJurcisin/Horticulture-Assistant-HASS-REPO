from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ChatApi
from .engine import guidelines  # type: ignore[import]
from .storage import LocalStore
from .utils.logging import warn_once

_LOGGER = logging.getLogger(__name__)


class HortiAICoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator handling slow AI calls."""

    def __init__(
        self,
        hass,
        api: ChatApi,
        store: LocalStore,
        update_minutes: int,
        initial: str | None = None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="horticulture_assistant_ai",
            update_interval=timedelta(minutes=update_minutes),
        )
        self.api = api
        self.store = store
        self.store_data = store.data or {}
        self.retry_count = 0
        self.breaker_open = False
        self._breaker_until: datetime | None = None
        self.latency_ms: int | None = None
        self.last_call: datetime | None = None
        self.last_exception_msg: str | None = None
        if initial:
            self.data = {"ok": True, "recommendation": initial}

    async def async_request_refresh(self) -> None:
        """Refresh immediately without the built-in debouncer."""
        await self._async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        if self.breaker_open and self._breaker_until and now < self._breaker_until:
            warn_once(
                _LOGGER,
                "BREAKER",
                f"Skipping AI update; breaker open until {self._breaker_until}",
            )
            self.last_call = now
            return self.data or {}

        start = time.monotonic()
        self.last_call = now
        try:
            profile = self.store_data.get("profile", {})
            plant_type = profile.get("plant_type", "tomato")
            stage = profile.get("stage")
            summary = guidelines.get_guideline_summary(plant_type, stage)
            messages = [
                {"role": "system", "content": "You are a horticulture assistant."},
                {
                    "role": "user",
                    "content": (
                        f"Profile: {profile}\nGuidelines: {json.dumps(summary)}\n"
                        "Provide a concise recommendation."
                    ),
                },
            ]
            res = await self.api.chat(messages, temperature=0.2, max_tokens=256)
            self.retry_count = 0
            self.breaker_open = False
            self._breaker_until = None
            try:
                text = res["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                text = str(res)
            self.store_data["recommendation"] = text
            await self.store.save(self.store_data)
            self.latency_ms = int((time.monotonic() - start) * 1000)
            self.last_exception_msg = None
            return {"ok": True, "recommendation": text}
        except (TimeoutError, ClientError, ConnectionError, ValueError) as err:
            self.latency_ms = int((time.monotonic() - start) * 1000)
            self.retry_count += 1
            err_key = type(err).__name__

            if "429" in str(err):
                code = "API_429"
                warn_once(_LOGGER, code, "Rate limit exceeded; backing off.")
            elif isinstance(err, asyncio.TimeoutError):
                code = "TIMEOUT"
                warn_once(_LOGGER, code, "API request timed out")
            elif isinstance(err, ConnectionError):
                code = "CONNECTION_ERROR"
                warn_once(_LOGGER, code, "Connection error to AI service")
            elif isinstance(err, ValueError) and "non-blocking" in str(err):
                code = "SOCKET_NONBLOCKING"
                warn_once(_LOGGER, code, f"Socket must be non-blocking: {err}")
            else:
                code = err_key
                warn_once(_LOGGER, code, f"API error in AI coordinator: {err}")

            if self.retry_count > 3:
                self.breaker_open = True
                self._breaker_until = dt_util.utcnow() + timedelta(minutes=5)
                _LOGGER.error("AI update failed; breaker opened (%s): %s", code, err)
            else:
                warn_once(_LOGGER, code, f"AI update failed ({code}): {err}")
            self.last_exception_msg = str(err)
            self.async_set_updated_data({"ok": False, "error": str(err)})
            raise UpdateFailed(f"AI update failed ({code}): {err}") from err
        except Exception as err:  # pragma: no cover - unexpected
            self.latency_ms = int((time.monotonic() - start) * 1000)
            self.retry_count += 1
            warn_once(
                _LOGGER, "UNEXPECTED", f"Unexpected error in AI coordinator: {err}"
            )
            _LOGGER.exception("AI update failed unexpectedly: %s", err)
            if self.retry_count > 3:
                self.breaker_open = True
                self._breaker_until = dt_util.utcnow() + timedelta(minutes=5)
            self.last_exception_msg = str(err)
            self.async_set_updated_data({"ok": False, "error": str(err)})
            raise UpdateFailed(f"AI update failed (UNEXPECTED): {err}") from err

    async def async_shutdown(self) -> None:
        """Shut down the coordinator (placeholder for future cleanup)."""
        return
