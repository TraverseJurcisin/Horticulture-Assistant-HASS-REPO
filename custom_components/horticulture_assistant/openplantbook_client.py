from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import asyncio
import logging

import aiohttp
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

try:
    from openplantbook_sdk import OpenPlantBookApi  # MIT-licensed SDK
except ImportError:  # pragma: no cover
    OpenPlantBookApi = None  # type: ignore[assignment]


_LOGGER = logging.getLogger(__name__)


class OpenPlantbookClient:
    """Minimal async wrapper around openplantbook-sdk + image download helpers."""

    def __init__(self, hass: HomeAssistant, client_id: str, secret: str) -> None:
        if OpenPlantBookApi is None:
            raise RuntimeError("openplantbook-sdk is not installed")
        self.hass = hass
        self._api = OpenPlantBookApi(client_id, secret)

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Return list of {pid, display} results for a free-text query."""
        res: dict[str, Any] = await self._api.async_plant_search(query)
        items: list[dict[str, Any]] = []
        for it in (res or {}).get("results", []):
            pid = it.get("pid") or it.get("species") or it.get("name")
            display = it.get("name") or it.get("display_name") or pid
            if pid:
                items.append({"pid": pid, "display": display})
        return items

    async def get_details(self, pid: str) -> dict[str, Any]:
        """Return full plant details dict for a PID (thresholds, image_url, etc.)."""
        return await self._api.async_plant_detail_get(pid)

    async def download_image(
        self,
        species_name: str,
        image_url: str,
        download_dir: Path,
        rewrite_local_when_www: bool = True,
    ) -> Optional[str]:
        """Download image to download_dir; return URL path suitable for Lovelace.

        If path includes 'www/', return '/local/...'; otherwise return original URL.
        Never overwrites existing files.
        """
        if not image_url:
            return None

        await self.hass.async_add_executor_job(
            download_dir.mkdir, parents=True, exist_ok=True
        )
        url_path = Path(URL(image_url).path)
        ext = url_path.suffix or ".jpg"
        safe = slugify(species_name) if species_name else slugify(url_path.stem)
        dst = download_dir / f"{safe}{ext}"
        if not dst.exists():
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(
                    image_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.warning("Failed to download image %s: %s", image_url, err)
                return image_url
            try:
                await self.hass.async_add_executor_job(dst.write_bytes, data)
            except OSError as err:  # pragma: no cover - disk issues
                _LOGGER.warning("Failed to write image %s: %s", dst, err)
                return image_url

        if rewrite_local_when_www:
            www_path = Path(self.hass.config.path("www")).resolve()
            try:
                rel = dst.resolve().relative_to(www_path)
            except (FileNotFoundError, ValueError):
                pass
            else:
                return f"/local/{rel.as_posix()}"
        return image_url

    async def upload(
        self,
        custom_id: str,
        pid: str,
        sensors: dict[str, float],
        *,
        location_country: str | None = None,
        location_lon: float | None = None,
        location_lat: float | None = None,
        location_by_ip: bool | None = None,
    ) -> None:
        """Register plant instance and upload sensor data to OpenPlantbook."""
        from datetime import datetime
        from json_timeseries import JtsDocument, TimeSeries, TsRecord

        await self._api.async_plant_instance_register(
            {custom_id: pid},
            location_by_ip=location_by_ip,
            location_country=location_country,
            location_lon=location_lon,
            location_lat=location_lat,
        )

        doc = JtsDocument()
        now = datetime.utcnow()
        for name, value in sensors.items():
            ts = TimeSeries(name)
            ts.insert(TsRecord(now, value))
            doc.addSeries(ts)

        await self._api.async_plant_data_upload(doc)
