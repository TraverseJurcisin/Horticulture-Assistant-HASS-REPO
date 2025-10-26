from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiohttp

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

BASE_URL = "https://api.openplantbook.org"
_SPECIES_CACHE: dict[str, tuple[dict[str, Any], datetime]] = {}
_SEARCH_CACHE: dict[str, tuple[list[dict[str, Any]], datetime]] = {}
_CACHE_TTL = timedelta(hours=12)
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class OpenPlantbookError(Exception): ...


class OpenPlantbookClient:
    def __init__(
        self,
        session_or_hass: aiohttp.ClientSession | Any,
        token_or_client_id: str | None,
        secret: str | None = None,
    ) -> None:
        """Wrap a session with optional bearer token headers."""

        session: aiohttp.ClientSession | None
        token: str | None

        if secret is None and hasattr(session_or_hass, "get"):
            session = session_or_hass
            token = token_or_client_id
            self._client_id = None
            self._secret = None
        else:
            hass = session_or_hass
            self._client_id = token_or_client_id
            self._secret = secret
            session = None
            helper = getattr(getattr(hass, "helpers", None), "aiohttp_client", None)
            if helper is not None:
                try:
                    session = helper.async_get_clientsession(hass)
                except Exception:  # pragma: no cover - helper unavailable in tests
                    session = None
            token = secret

        self._s = session
        self._h = {"Authorization": f"Bearer {token}"} if token else {}

    async def _get(self, path: str) -> Any:
        if self._s is None:
            raise OpenPlantbookError("client session unavailable")
        url = f"{BASE_URL}{path}"
        try:
            async with self._s.get(url, headers=self._h, timeout=_TIMEOUT) as r:
                if r.status != 200:
                    raise OpenPlantbookError(f"request failed: {r.status}")
                try:
                    return await r.json()
                except aiohttp.ContentTypeError as err:
                    raise OpenPlantbookError("invalid response") from err
        except (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError) as err:  # noqa: UP041
            raise OpenPlantbookError(str(err)) from err

    async def species_details(self, slug: str) -> dict[str, Any]:
        data = await self._get(f"/v1/species/{slug}")
        return data if isinstance(data, dict) else {}

    async def search(self, query: str) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        cached = _SEARCH_CACHE.get(query)
        if cached and now - cached[1] < _CACHE_TTL:
            return cached[0]
        data = await self._get(f"/v1/species?search={query}")
        results = data if isinstance(data, list) else []
        _SEARCH_CACHE[query] = (results, now)
        return results

    async def get_details(self, pid: str) -> dict[str, Any]:
        """Fetch species details for ``pid``."""

        detail = await self.species_details(pid)
        return detail if isinstance(detail, dict) else {}

    async def download_image(self, _name: str, _image_url: str, _target_dir: Path | str) -> str | None:
        """Placeholder image downloader.

        The real integration stores the file locally and returns a URL. Tests
        patch this method, so the default implementation simply indicates no
        download occurred.
        """

        return None


async def async_fetch_field(hass, species: str, field: str, token: str | None = None) -> tuple[float | None, str]:
    """Fetch a numeric field for a species from OpenPlantbook.

    Returns a `(value, url)` tuple where ``value`` is coerced to ``float`` when
    possible, otherwise ``None``. ``url`` points to the species detail page so
    it can be used for citation links.
    """
    session = hass.helpers.aiohttp_client.async_get_clientsession()
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
    """Clear cached species and search lookups."""
    _SPECIES_CACHE.clear()
    _SEARCH_CACHE.clear()
