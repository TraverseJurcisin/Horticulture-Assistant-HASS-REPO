from __future__ import annotations

from functools import lru_cache
from homeassistant.core import HomeAssistant


@lru_cache(maxsize=8)
def _parse_large_file_sync(path: str) -> dict:
    import json
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


async def load_large_json(hass: HomeAssistant, path: str) -> dict:
    return await hass.async_add_executor_job(_parse_large_file_sync, path)
