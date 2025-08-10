from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ChatApi
from .plant_engine import guidelines  # type: ignore[import]
from .storage import LocalStore
from .utils.log_utils import log_limited

_LOGGER = logging.getLogger(__name__)


class HortiAICoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator handling slow AI calls."""

    def __init__(self, hass, api: ChatApi, store: LocalStore, update_minutes: int, initial: str | None = None):
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
        self.latency_ms: int | None = None
        self.last_call: datetime | None = None
        self.last_exception_msg: str | None = None
        if initial:
            self.data = {"ok": True, "recommendation": initial}

    async def _async_update_data(self) -> dict[str, Any]:
        start = time.monotonic()
        self.last_call = dt_util.utcnow()
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
            try:
                text = res["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                text = str(res)
            self.store_data["recommendation"] = text
            await self.store.save(self.store_data)
            self.latency_ms = int((time.monotonic() - start) * 1000)
            self.last_exception_msg = None
            return {"ok": True, "recommendation": text}
        except Exception as err:
            self.latency_ms = int((time.monotonic() - start) * 1000)
            self.retry_count += 1
            err_key = type(err).__name__
            code = "API_429" if "429" in str(err) else (
                "TIMEOUT" if isinstance(err, asyncio.TimeoutError) else err_key
            )
            if self.retry_count > 3:
                self.breaker_open = True
                _LOGGER.error("AI update failed; breaker opened (%s): %s", code, err)
            else:
                log_limited(_LOGGER, logging.WARNING, code, "AI update failed (%s): %s", code, err)
            self.last_exception_msg = str(err)
            raise UpdateFailed(str(err)) from err
