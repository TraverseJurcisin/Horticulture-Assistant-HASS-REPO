"""Helpers for authenticating against the Horticulture Assistant cloud API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

try:
    UTC = datetime.UTC  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


class CloudAuthError(RuntimeError):
    """Raised when the cloud API rejects credentials or returns malformed data."""


@dataclass(slots=True)
class CloudAuthTokens:
    """Normalised tokens returned by the cloud authentication endpoints."""

    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    tenant_id: str
    device_token: str | None = None
    account_email: str | None = None
    roles: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, now: datetime | None = None) -> CloudAuthTokens:
        """Create a :class:`CloudAuthTokens` from an API JSON payload."""

        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise CloudAuthError("access_token missing from response")

        tenant_id = str(payload.get("tenant_id") or "").strip()
        if not tenant_id:
            raise CloudAuthError("tenant_id missing from response")

        refresh = payload.get("refresh_token")
        refresh_token = str(refresh).strip() if refresh else None

        expires_at: datetime | None = None
        expiry = payload.get("expires_at") or payload.get("expiry")
        if isinstance(expiry, int | float):
            now = now or datetime.now(tz=UTC)
            expires_at = now + timedelta(seconds=float(expiry))
        elif isinstance(expiry, str) and expiry:
            try:
                parsed = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            except ValueError as err:
                raise CloudAuthError(f"invalid expiry timestamp: {expiry}") from err
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            expires_at = parsed.astimezone(UTC)

        roles_raw = payload.get("roles")
        if isinstance(roles_raw, list | tuple | set):
            roles = tuple(sorted({str(role) for role in roles_raw if role}))
        elif isinstance(roles_raw, str) and roles_raw:
            roles = (roles_raw,)
        else:
            roles = ()

        email = payload.get("account") or payload.get("email")
        account_email = str(email).strip() if email else None

        device_token = payload.get("device_token")
        device_token_str = str(device_token).strip() if device_token else None

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            tenant_id=tenant_id,
            device_token=device_token_str or None,
            account_email=account_email or None,
            roles=roles,
        )

    def to_options(self) -> dict[str, Any]:
        """Serialise the token metadata for storage in config entry options."""

        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tenant_id": self.tenant_id,
            "device_token": self.device_token,
            "account_email": self.account_email,
            "roles": list(self.roles),
        }

    def is_expired(self, *, now: datetime | None = None, threshold_seconds: int = 0) -> bool:
        """Return ``True`` if the access token has expired or is close to expiry."""

        if self.expires_at is None:
            return False
        now = now or datetime.now(tz=UTC)
        return (self.expires_at - now).total_seconds() <= threshold_seconds


class CloudAuthClient:
    """Simple API wrapper used by the config flow and services."""

    def __init__(self, base_url: str, session: ClientSession | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or ClientSession()
        self._owns_session = session is None

    async def async_close(self) -> None:
        if self._owns_session and not self._session.closed:
            await self._session.close()

    async def async_login(self, email: str, password: str) -> CloudAuthTokens:
        """Authenticate with the cloud API using email/password credentials."""

        payload = {"email": email, "password": password}
        try:
            async with self._session.post(f"{self._base_url}/auth/login", json=payload, timeout=30) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    message = data.get("message") if isinstance(data, Mapping) else None
                    raise CloudAuthError(message or f"login failed: HTTP {resp.status}")
        except ClientResponseError as err:  # pragma: no cover - defensive logging
            raise CloudAuthError(f"login failed: {err}") from err
        except ClientError as err:
            raise CloudAuthError(f"login request failed: {err}") from err

        return CloudAuthTokens.from_payload(data)

    async def async_refresh(self, refresh_token: str) -> CloudAuthTokens:
        """Refresh an access token using the stored refresh token."""

        payload = {"refresh_token": refresh_token}
        try:
            async with self._session.post(f"{self._base_url}/auth/refresh", json=payload, timeout=30) as resp:
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    message = data.get("message") if isinstance(data, Mapping) else None
                    raise CloudAuthError(message or f"refresh failed: HTTP {resp.status}")
        except ClientResponseError as err:  # pragma: no cover - defensive logging
            raise CloudAuthError(f"refresh failed: {err}") from err
        except ClientError as err:
            raise CloudAuthError(f"refresh request failed: {err}") from err

        return CloudAuthTokens.from_payload(data)


__all__ = [
    "CloudAuthClient",
    "CloudAuthError",
    "CloudAuthTokens",
]
