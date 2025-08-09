from __future__ import annotations
import json
from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import ChatApi
from .storage import LocalStore
from .plant_engine import guidelines  # type: ignore[import]


class HortiCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, api: ChatApi, store: LocalStore, update_minutes: int, initial: str | None = None):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="horticulture_assistant",
            update_interval=timedelta(minutes=update_minutes),
        )
        self.api = api
        self.store = store
        self.store_data = store.data or {}
        if initial:
            self.data = {"ok": True, "recommendation": initial}

    async def _async_update_data(self) -> dict:
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
            try:
                text = res["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                text = str(res)
            self.store_data["recommendation"] = text
            await self.store.save(self.store_data)
            return {"ok": True, "recommendation": text}
        except Exception as err:
            raise UpdateFailed(str(err)) from err
