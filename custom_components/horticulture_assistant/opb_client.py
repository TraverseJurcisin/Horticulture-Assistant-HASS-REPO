from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

BASE_URL = "https://api.openplantbook.org"
_SPECIES_CACHE: dict[str, tuple[dict[str, Any], datetime]] = {}
_CACHE_TTL = timedelta(hours=12)


class OpenPlantbookError(Exception): ...


class OpenPlantbookClient:
    def __init__(self, session: aiohttp.ClientSession, token: str):
        self._s = session
        self._h = {"Authorization": f"Bearer {token}"} if token else {}

    async def species_details(self, slug: str) -> dict[str, Any]:
        url = f"{BASE_URL}/v1/species/{slug}"
        async with self._s.get(url, headers=self._h, timeout=20) as r:
            if r.status != 200:
                raise OpenPlantbookError(f"details failed: {r.status}")
            return await r.json()

    async def search(self, query: str) -> list[dict[str, Any]]:
        url = f"{BASE_URL}/v1/species?search={query}"
        async with self._s.get(url, headers=self._h, timeout=20) as r:
            if r.status != 200:
                raise OpenPlantbookError(f"search failed: {r.status}")
            data = await r.json()
            return data if isinstance(data, list) else []


async def async_fetch_field(hass, species: str, field: str) -> tuple[float | None, str]:
    """Fetch a numeric field for a species from OpenPlantbook.

    Returns a `(value, url)` tuple where ``value`` is coerced to ``float`` when
    possible, otherwise ``None``. ``url`` points to the species detail page so
    it can be used for citation links.
    """
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    token = None
    client = OpenPlantbookClient(session, token)
    now = datetime.now(UTC)
    cached = _SPECIES_CACHE.get(species)
    if cached and now - cached[1] < _CACHE_TTL:
        detail = cached[0]
    else:
        detail = await client.species_details(species)
        _SPECIES_CACHE[species] = (detail, now)
    cur: Any = detail
    for part in field.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
            break
    url = f"https://openplantbook.org/{species}"
    try:
        return float(cur), url
    except (TypeError, ValueError):
        return None, url


def clear_opb_cache() -> None:
    """Clear cached species lookups."""
    _SPECIES_CACHE.clear()
