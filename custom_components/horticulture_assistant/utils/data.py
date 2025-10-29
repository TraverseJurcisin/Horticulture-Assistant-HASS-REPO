from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

from homeassistant.core import HomeAssistant


@lru_cache(maxsize=8)
def _parse_large_file_sync(path: str) -> dict[str, Any]:
    import json

    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _load_cached_json(path: str) -> dict[str, Any]:
    """Return a deep copy of the cached payload for ``path``."""

    return deepcopy(_parse_large_file_sync(path))


async def load_large_json(hass: HomeAssistant, path: str) -> dict[str, Any]:
    """Load ``path`` as JSON using a cached reader while avoiding shared state."""

    return await hass.async_add_executor_job(_load_cached_json, path)
