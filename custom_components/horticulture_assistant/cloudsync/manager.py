"""Manage the edge sync worker lifecycle inside Home Assistant."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
    DEFAULT_CLOUD_SYNC_INTERVAL,
)
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


@dataclass(slots=True)
class CloudSyncConfig:
    """Configuration required to run the edge sync worker."""

    enabled: bool = False
    base_url: str = ""
    tenant_id: str = ""
    device_token: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: str | None = None
    account_email: str | None = None
    roles: tuple[str, ...] = ()
    interval: int = DEFAULT_CLOUD_SYNC_INTERVAL

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> CloudSyncConfig:
        enabled = bool(options.get(CONF_CLOUD_SYNC_ENABLED, False))
        base_url = str(options.get(CONF_CLOUD_BASE_URL, "") or "").strip()
        tenant_id = str(options.get(CONF_CLOUD_TENANT_ID, "") or "").strip()
        device_token = str(options.get(CONF_CLOUD_DEVICE_TOKEN, "") or "").strip()
        access_token = str(options.get(CONF_CLOUD_ACCESS_TOKEN, "") or "").strip()
        refresh_token = str(options.get(CONF_CLOUD_REFRESH_TOKEN, "") or "").strip()
        expires_raw = options.get(CONF_CLOUD_TOKEN_EXPIRES_AT)
        expires_at = str(expires_raw).strip() if expires_raw else None
        account_email = str(options.get(CONF_CLOUD_ACCOUNT_EMAIL, "") or "").strip() or None
        roles_raw = options.get(CONF_CLOUD_ACCOUNT_ROLES)
        if isinstance(roles_raw, list | tuple | set):
            roles = tuple(str(role) for role in roles_raw if role)
        elif isinstance(roles_raw, str) and roles_raw:
            roles = (roles_raw,)
        else:
            roles = ()
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
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            account_email=account_email,
            roles=roles,
            interval=interval,
        )

    @property
    def ready(self) -> bool:
        has_token = bool(self.device_token or self.access_token)
        return bool(self.enabled and self.base_url and self.tenant_id and has_token)

    def parsed_expiry(self) -> datetime | None:
        if not self.token_expires_at:
            return None
        try:
            parsed = datetime.fromisoformat(str(self.token_expires_at).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def token_expired(self, *, now: datetime | None = None, threshold_seconds: int = 0) -> bool:
        expiry = self.parsed_expiry()
        if expiry is None:
            return False
        now = now or datetime.now(tz=UTC)
        return (expiry - now).total_seconds() <= threshold_seconds


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
            self.config.device_token or self.config.access_token,
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

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        """Return runtime status information for diagnostics and sensors."""

        now = now or datetime.now(tz=UTC)
        status: dict[str, Any] = {
            "enabled": self.config.enabled,
            "configured": self.config.ready,
            "store_path": str(self.store_path),
            "outbox_size": self.store.outbox_size(),
            "cloud_cache_entries": self.store.count_cloud_cache(),
            "cloud_snapshot_age_days": self.store.cloud_cache_age(now=now),
            "cloud_snapshot_oldest_age_days": self.store.cloud_cache_oldest_age(now=now),
            "account_email": self.config.account_email,
            "tenant_id": self.config.tenant_id,
            "roles": list(self.config.roles),
            "token_expires_at": self.config.token_expires_at,
            "refresh_token": bool(self.config.refresh_token),
        }
        if self._worker:
            status.update(self._worker.status())
        expiry = self.config.parsed_expiry()
        if expiry is not None:
            status["token_expires_in_seconds"] = max((expiry - now).total_seconds(), 0.0)
        status["token_expired"] = self.config.token_expired(now=now, threshold_seconds=30)
        status["connection"] = self._connection_summary(status, now)
        return status

    # ------------------------------------------------------------------
    def _connection_summary(self, status: Mapping[str, Any], now: datetime) -> dict[str, Any]:
        configured = bool(status.get("configured"))
        summary: dict[str, Any] = {
            "configured": configured,
            "connected": False,
            "local_only": not configured,
            "reason": "not_configured" if not configured else None,
            "last_success_at": status.get("last_success_at"),
            "last_success_age_seconds": None,
            "last_success_age_days": None,
        }
        if not configured:
            return summary

        if status.get("token_expired"):
            summary["reason"] = "token_expired"
            summary["local_only"] = True
            return summary

        last_success_raw = status.get("last_success_at")
        if not last_success_raw:
            summary["local_only"] = True
            summary["reason"] = "never_synced"
            return summary

        last_success = self._parse_timestamp(str(last_success_raw))
        if last_success is None:
            summary["local_only"] = True
            summary["reason"] = "invalid_timestamp"
            return summary

        age_seconds = max((now - last_success).total_seconds(), 0.0)
        summary["last_success_age_seconds"] = age_seconds
        summary["last_success_age_days"] = age_seconds / 86400 if age_seconds else 0.0

        error = status.get("last_pull_error") or status.get("last_push_error")
        threshold_seconds = max(self.config.interval * 2, 300)
        if error:
            summary["reason"] = "recent_error"
            summary["local_only"] = True
            return summary
        if age_seconds > threshold_seconds:
            summary["reason"] = "stale"
            summary["local_only"] = True
            return summary

        summary["connected"] = True
        summary["local_only"] = False
        summary["reason"] = None
        return summary

    def _parse_timestamp(self, raw: str) -> datetime | None:
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
