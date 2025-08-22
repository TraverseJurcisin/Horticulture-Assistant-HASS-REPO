from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

BASE_URL = "https://api.openplantbook.org"


class OpenPlantbookError(Exception):
    """Raised when OpenPlantbook API request fails."""


class OpenPlantbookClient:
    """Minimal OpenPlantbook API client using aiohttp."""

    def __init__(self, hass: HomeAssistant, client_id: str, secret: str) -> None:
        self._session = async_get_clientsession(hass)
        self._client_id = client_id
        self._secret = secret
        self._token: str | None = None

    async def _ensure_token(self) -> None:
        if self._token is not None:
            return
        async with self._session.post(
            f"{BASE_URL}/oauth2/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._secret,
            },
            timeout=20,
        ) as resp:
            if resp.status != 200:
                raise OpenPlantbookError(f"token failed: {resp.status}")
            data = await resp.json()
            token = data.get("access_token")
            if not token:
                raise OpenPlantbookError("missing token")
            self._token = token

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        await self._ensure_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"  # type: ignore[unreachable]
        async with self._session.request(method, url, headers=headers, timeout=20, **kwargs) as resp:
            if resp.status != 200:
                raise OpenPlantbookError(f"{method} {url} failed: {resp.status}")
            if resp.content_type == "application/json":
                return await resp.json()
            return await resp.read()

    async def search(self, query: str) -> list[dict[str, str]]:
        """Return list of {pid, display} dicts for a free-text query."""
        url = f"{BASE_URL}/v1/species?search={query}"
        data = await self._request("GET", url)
        results: list[dict[str, str]] = []
        for item in data.get("results", []):
            pid = item.get("pid") or item.get("species") or item.get("name")
            display = item.get("name") or item.get("display_name") or pid
            if pid:
                results.append({"pid": pid, "display": display or pid})
        return results

    async def get_details(self, pid: str) -> dict[str, Any]:
        """Return detailed species information for a PID."""
        url = f"{BASE_URL}/v1/species/{pid}"
        return await self._request("GET", url)

    async def download_image(self, name: str, url: str, directory: Path) -> str | None:
        """Download image to directory; return local /local path or original URL."""
        try:
            data = await self._request("GET", url)
        except OpenPlantbookError:
            return url
        directory.mkdir(parents=True, exist_ok=True)
        slug = slugify(name) or "plant"
        ext = Path(urlparse(url).path).suffix or ".jpg"
        path = directory / f"{slug}{ext}"
        path.write_bytes(data)
        try:
            www = Path(directory).parents[1]
            return f"/local/{path.relative_to(www)}"
        except ValueError:
            return url

    async def upload(self, plant_id: str, pid: str, values: dict[str, float], **kwargs) -> None:
        """Upload observation values for a plant species."""
        url = f"{BASE_URL}/v1/observations/{pid}"
        payload = {"plant_id": plant_id, "values": values, **kwargs}
        await self._request("POST", url, json=payload)
