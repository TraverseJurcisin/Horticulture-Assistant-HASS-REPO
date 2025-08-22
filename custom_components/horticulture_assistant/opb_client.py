from __future__ import annotations

from typing import Any

import aiohttp

BASE_URL = "https://api.openplantbook.org"


class OpenPlantbookError(Exception):
    ...


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


async def async_fetch_field(hass, species: str, field: str) -> tuple[Any, str]:
    """Fetch a specific field for a species from OpenPlantbook."""
    session = hass.helpers.aiohttp_client.async_get_clientsession()
    token = None
    client = OpenPlantbookClient(session, token)
    detail = await client.species_details(species)
    cur: Any = detail
    for part in field.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
            break
    url = f"https://openplantbook.org/{species}"
    return cur, url
