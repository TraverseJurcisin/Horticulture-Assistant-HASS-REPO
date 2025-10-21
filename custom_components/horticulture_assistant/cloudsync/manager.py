"""Manage the edge sync worker lifecycle inside Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    DEFAULT_CLOUD_SYNC_INTERVAL,
)
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker


@dataclass(slots=True)
class CloudSyncConfig:
    """Configuration required to run the edge sync worker."""

    enabled: bool = False
    base_url: str = ""
    tenant_id: str = ""
    device_token: str = ""
    interval: int = DEFAULT_CLOUD_SYNC_INTERVAL

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> CloudSyncConfig:
        enabled = bool(options.get(CONF_CLOUD_SYNC_ENABLED, False))
        base_url = str(options.get(CONF_CLOUD_BASE_URL, "") or "").strip()
        tenant_id = str(options.get(CONF_CLOUD_TENANT_ID, "") or "").strip()
        device_token = str(options.get(CONF_CLOUD_DEVICE_TOKEN, "") or "").strip()
        interval_raw = options.get(CONF_CLOUD_SYNC_INTERVAL, DEFAULT_CLOUD_SYNC_INTERVAL)
        try:
            interval = max(15, int(interval_raw))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            interval = DEFAULT_CLOUD_SYNC_INTERVAL
        return cls(
            enabled=enabled,
            base_url=base_url,
            tenant_id=tenant_id,
            device_token=device_token,
            interval=interval,
        )

    @property
    def ready(self) -> bool:
        return bool(self.enabled and self.base_url and self.tenant_id and self.device_token)


class CloudSyncManager:
    """Wrapper that ties :class:`EdgeSyncWorker` into Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry,
        *,
        store_path: Path | None = None,
        session: ClientSession | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.config = CloudSyncConfig.from_options(entry.options)
        base_dir = Path(hass.config.path("horticulture_assistant", "cloudsync"))
        self.store_path = store_path or base_dir / f"{entry.entry_id or 'default'}.db"
        self.store = EdgeSyncStore(self.store_path)
        self._session = session
        self._owns_session = session is None
        self._worker: EdgeSyncWorker | None = None
        self._task: asyncio.Task | None = None

    async def async_start(self) -> None:
        """Start the sync worker when configuration is complete."""

        self.config = CloudSyncConfig.from_options(self.entry.options)
        if not self.config.ready:
            await self.async_stop()
            return
        if self._task and not self._task.done():
            return
        if self._session is None:
            self._session = ClientSession()
            self._owns_session = True
        self._worker = EdgeSyncWorker(
            self.store,
            self._session,
            self.config.base_url,
            self.config.device_token,
            self.config.tenant_id,
        )
        self._task = self.hass.async_create_task(self._worker.run_forever(interval_seconds=self.config.interval))

    async def async_stop(self) -> None:
        """Stop the sync worker and release resources."""

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        self._worker = None
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._owns_session = False

    async def async_refresh(self) -> None:
        """Restart the worker with updated configuration."""

        await self.async_stop()
        await self.async_start()

    def status(self) -> dict[str, Any]:
        """Return runtime status information for diagnostics."""

        status: dict[str, Any] = {
            "enabled": self.config.enabled,
            "configured": self.config.ready,
            "store_path": str(self.store_path),
        }
        if self._worker:
            status.update(self._worker.status())
        return status
