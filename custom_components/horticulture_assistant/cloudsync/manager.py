"""Manage the edge sync worker lifecycle inside Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_AVAILABLE_ORGANIZATIONS,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_ORGANIZATION_ID,
    CONF_CLOUD_ORGANIZATION_NAME,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
    DEFAULT_CLOUD_SYNC_INTERVAL,
)
from .auth import CloudAuthClient, CloudAuthError, CloudAuthTokens
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker
from .options import merge_cloud_tokens

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


_LOGGER = logging.getLogger(__name__)


class CloudSyncError(RuntimeError):
    """Raised when a manual sync operation cannot be completed."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


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
    organization_id: str | None = None
    organization_name: str | None = None
    organization_role: str | None = None
    available_organizations: tuple[dict[str, Any], ...] = ()

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
        org_id = str(options.get(CONF_CLOUD_ORGANIZATION_ID, "") or "").strip() or None
        org_name = str(options.get(CONF_CLOUD_ORGANIZATION_NAME, "") or "").strip() or None
        org_role = str(options.get(CONF_CLOUD_ORGANIZATION_ROLE, "") or "").strip() or None
        orgs_raw = options.get(CONF_CLOUD_AVAILABLE_ORGANIZATIONS)
        if isinstance(orgs_raw, list):
            processed: list[dict[str, Any]] = []
            for item in orgs_raw:
                if not isinstance(item, Mapping):
                    continue
                org_candidate = str(item.get("id") or item.get("org_id") or "").strip()
                if not org_candidate:
                    continue
                name_candidate = str(item.get("name") or item.get("label") or "").strip() or None
                processed.append(
                    {
                        "id": org_candidate,
                        "name": name_candidate,
                        "roles": item.get("roles"),
                        "default": item.get("default"),
                    }
                )
            available_orgs = tuple(processed)
        else:
            available_orgs = ()
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
            organization_id=org_id,
            organization_name=org_name,
            organization_role=org_role,
            available_organizations=available_orgs,
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
        self._refresh_task: asyncio.Task | None = None
        self._next_refresh_at: datetime | None = None
        self._token_listeners: list[Callable[[Mapping[str, Any]], Awaitable[None] | None]] = []
        self._last_token_refresh_at: datetime | None = None
        self._last_token_refresh_error: str | None = None
        self._last_offline_enqueue_at: datetime | None = None
        self._offline_queue_reason: str | None = None
        self._sync_lock = asyncio.Lock()
        self._last_manual_sync_at: datetime | None = None
        self._last_manual_sync_result: dict[str, Any] | None = None
        self._last_manual_sync_error: str | None = None

    async def async_start(self) -> None:
        """Start the sync worker when configuration is complete."""

        self.config = CloudSyncConfig.from_options(self.entry.options)
        if not self.config.ready:
            await self.async_stop()
            return
        if self._task and not self._task.done():
            return
        self._offline_queue_reason = None
        if self._session is None:
            self._session = ClientSession()
            self._owns_session = True
        self._worker = self._create_worker(self._session)
        self._task = self.hass.async_create_task(self._worker.run_forever(interval_seconds=self.config.interval))
        self._schedule_token_refresh()

    def _create_worker(self, session: ClientSession) -> EdgeSyncWorker:
        if not self.config.ready:
            raise CloudSyncError("cloud sync is not fully configured", reason="not_configured")
        return EdgeSyncWorker(
            self.store,
            session,
            self.config.base_url,
            self.config.device_token or self.config.access_token,
            self.config.tenant_id,
            organization_id=self.config.organization_id,
        )

    async def async_stop(self) -> None:
        """Stop the sync worker and release resources."""

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        self._worker = None
        if self._refresh_task:
            self._refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._refresh_task
        self._refresh_task = None
        self._next_refresh_at = None
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
            "organization_id": self.config.organization_id,
            "organization_name": self.config.organization_name,
            "organization_role": self.config.organization_role,
            "organizations": [dict(org) for org in self.config.available_organizations],
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
        status["last_token_refresh_at"] = (
            self._last_token_refresh_at.isoformat() if self._last_token_refresh_at else None
        )
        status["last_token_refresh_error"] = self._last_token_refresh_error
        if self._next_refresh_at is not None:
            status["next_token_refresh_at"] = self._next_refresh_at.isoformat()
            status["next_token_refresh_in_seconds"] = max(
                (self._next_refresh_at - now).total_seconds(),
                0.0,
            )
        else:
            status["next_token_refresh_at"] = None
            status["next_token_refresh_in_seconds"] = None
        status["connection"] = self._connection_summary(status, now)
        status["offline_queue"] = {
            "pending": status["outbox_size"],
            "last_enqueued_at": self._last_offline_enqueue_at.isoformat() if self._last_offline_enqueue_at else None,
            "reason": self._offline_queue_reason,
            "queueing": bool(self._offline_queue_reason),
            "last_error": status.get("last_push_error") or status.get("last_pull_error"),
        }
        if not status["offline_queue"]["pending"]:
            status["offline_queue"]["queueing"] = False
            status["offline_queue"]["reason"] = None
            self._offline_queue_reason = None
        elif not status["offline_queue"]["reason"]:
            if status.get("last_push_error"):
                status["offline_queue"]["reason"] = "push_error"
            elif status.get("last_pull_error"):
                status["offline_queue"]["reason"] = "pull_error"
        status["manual_sync"] = {
            "last_run_at": self._last_manual_sync_at.isoformat() if self._last_manual_sync_at else None,
            "result": dict(self._last_manual_sync_result) if self._last_manual_sync_result else None,
            "error": self._last_manual_sync_error,
        }
        return status

    async def async_sync_now(self, *, push: bool = True, pull: bool = True) -> dict[str, Any]:
        """Perform a one-off sync cycle for the configured tenant."""

        if not push and not pull:
            raise CloudSyncError("at least one of push/pull must be enabled", reason="invalid_request")
        self.config = CloudSyncConfig.from_options(self.entry.options)
        if not self.config.ready:
            raise CloudSyncError("cloud sync is not fully configured", reason="not_configured")

        async with self._sync_lock:
            was_running = self._task is not None and not self._task.done()
            session = self._session
            owns_session = False
            if was_running:
                await self.async_stop()
                session = None

            if session is None:
                session = ClientSession()
                owns_session = True

            worker = self._create_worker(session)
            pushed = pulled = 0
            error: Exception | None = None
            try:
                if push:
                    pushed = await worker.push_once()
                if pull:
                    pulled = await worker.pull_once()
            except Exception as err:  # pragma: no cover - propagated to caller
                error = err
                self._last_manual_sync_error = str(err)
                self._last_manual_sync_result = None
                self._last_manual_sync_at = datetime.now(tz=UTC)
                raise CloudSyncError(str(err), reason="sync_failed") from err
            finally:
                if owns_session:
                    await session.close()
                if was_running:
                    await self.async_start()
                if error is None and self.store.outbox_size() == 0:
                    self._offline_queue_reason = None

            now = datetime.now(tz=UTC)
            self._last_manual_sync_at = now
            self._last_manual_sync_result = {"pushed": pushed, "pulled": pulled}
            self._last_manual_sync_error = None
            status = self.status(now=now)
            return {
                "pushed": pushed,
                "pulled": pulled,
                "status": status,
            }

    # ------------------------------------------------------------------
    def register_token_listener(self, listener: Callable[[Mapping[str, Any]], Awaitable[None] | None]) -> None:
        """Register a callback invoked when cloud token options change."""

        if listener in self._token_listeners:
            return
        self._token_listeners.append(listener)

    async def async_update_tokens(self, tokens: CloudAuthTokens, *, base_url: str) -> dict[str, Any]:
        """Persist refreshed tokens to the config entry and restart sync."""

        opts = merge_cloud_tokens(self.entry.options, tokens, base_url=base_url)
        self.hass.config_entries.async_update_entry(self.entry, options=opts)
        self.entry.options = opts
        self.config = CloudSyncConfig.from_options(opts)
        await self.async_refresh()
        await self._notify_token_listeners(opts)
        return opts

    async def async_trigger_token_refresh(
        self,
        *,
        force: bool = False,
        base_url: str | None = None,
    ) -> dict[str, Any] | None:
        """Refresh the cloud access token when expired or when forced."""

        refresh_token = self.config.refresh_token
        if not refresh_token:
            return None
        if not force and not self.config.token_expired(threshold_seconds=300):
            return None
        base_url = base_url or self.config.base_url
        if not base_url:
            raise CloudAuthError("cloud base URL missing for token refresh")

        client = CloudAuthClient(base_url)
        try:
            tokens = await client.async_refresh(refresh_token)
        except CloudAuthError as err:
            self._last_token_refresh_at = datetime.now(tz=UTC)
            self._last_token_refresh_error = str(err)
            raise
        finally:
            await client.async_close()

        opts = await self.async_update_tokens(tokens, base_url=base_url)
        self._last_token_refresh_at = datetime.now(tz=UTC)
        self._last_token_refresh_error = None
        return opts

    async def _notify_token_listeners(self, options: Mapping[str, Any]) -> None:
        for listener in list(self._token_listeners):
            try:
                result = listener(options)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as err:  # pragma: no cover - defensive log
                _LOGGER.debug("Token listener raised error: %s", err, exc_info=True)

    def _schedule_token_refresh(self, *, fallback_seconds: int | None = None) -> None:
        refresh_token = self.config.refresh_token
        base_url = self.config.base_url
        if not refresh_token or not base_url:
            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()
            self._refresh_task = None
            self._next_refresh_at = None
            return

        current = asyncio.current_task()
        if self._refresh_task and not self._refresh_task.done() and self._refresh_task is not current:
            self._refresh_task.cancel()
        if self._refresh_task and self._refresh_task is current:
            self._refresh_task = None

        expiry = self.config.parsed_expiry()
        if expiry is None:
            if fallback_seconds is None:
                self._next_refresh_at = None
                return
            delay = max(float(fallback_seconds), 0.0)
        else:
            now = datetime.now(tz=UTC)
            delay = (expiry - now).total_seconds() - 300
            if delay < 0:
                delay = 0.0
            if delay == 0.0 and fallback_seconds:
                delay = max(float(fallback_seconds), 0.0)
        self._next_refresh_at = datetime.now(tz=UTC) + timedelta(seconds=delay)
        self._refresh_task = self.hass.async_create_task(self._auto_refresh_loop(delay))

    async def _auto_refresh_loop(self, delay: float) -> None:
        current = asyncio.current_task()
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                await self.async_trigger_token_refresh()
            except CloudAuthError as err:
                self._last_token_refresh_error = str(err)
                _LOGGER.warning("Automatic token refresh failed: %s", err)
                self._schedule_token_refresh(fallback_seconds=300)
        except asyncio.CancelledError:
            raise
        finally:
            if self._refresh_task is current:
                self._refresh_task = None
                self._next_refresh_at = None

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
        summary["queueing"] = bool(status.get("outbox_size"))
        if not configured:
            return summary

        if status.get("token_expired"):
            summary["reason"] = "token_expired"
            summary["local_only"] = True
            if summary["queueing"] and summary.get("reason") is None:
                summary["reason"] = "pending_sync"
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
        if summary["queueing"] and summary.get("reason") is None and summary.get("local_only"):
            summary["reason"] = "pending_sync"
        return summary

    def record_offline_enqueue(self, *, reason: str) -> None:
        """Track when events are queued while the cloud connection is unavailable."""

        self._last_offline_enqueue_at = datetime.now(tz=UTC)
        self._offline_queue_reason = reason

    def _parse_timestamp(self, raw: str) -> datetime | None:
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
