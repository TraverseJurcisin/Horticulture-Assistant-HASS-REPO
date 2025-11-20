"""Helpers for authenticating against the Horticulture Assistant cloud API."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..utils.aiohttp import ClientError, ClientResponseError, ClientSession

try:
    from datetime import UTC
except ImportError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


class CloudAuthError(RuntimeError):
    """Raised when the cloud API rejects credentials or returns malformed data."""


@dataclass(slots=True)
class CloudOrganization:
    """Represents a single organization returned by the cloud API."""

    org_id: str
    name: str | None = None
    roles: tuple[str, ...] = ()
    default: bool = False

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> CloudOrganization:
        org_id = str(payload.get("id") or payload.get("org_id") or payload.get("organization_id") or "").strip()
        if not org_id:
            raise CloudAuthError("organization payload missing id")
        name_raw = payload.get("name") or payload.get("label")
        name = str(name_raw).strip() if name_raw else None
        roles_raw = payload.get("roles") or payload.get("role") or ()
        if isinstance(roles_raw, str):
            roles = (roles_raw,)
        elif isinstance(roles_raw, list | tuple | set):
            roles = tuple(str(role) for role in roles_raw if role)
        else:
            roles = ()
        default = bool(payload.get("default") or payload.get("is_default"))
        return cls(org_id=org_id, name=name, roles=roles, default=default)

    def to_options(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.org_id,
            "name": self.name,
            "roles": list(self.roles),
            "default": self.default,
        }
        return {key: value for key, value in payload.items() if value is not None}


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
    organization_id: str | None = None
    organization_name: str | None = None
    organization_role: str | None = None
    organizations: tuple[CloudOrganization, ...] = ()

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
            text = expiry.strip()
            if text:
                try:
                    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        seconds = float(text)
                    except (TypeError, ValueError) as err:
                        raise CloudAuthError(f"invalid expiry timestamp: {expiry}") from err
                    now = now or datetime.now(tz=UTC)
                    expires_at = now + timedelta(seconds=seconds)
                else:
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=UTC)
                    expires_at = parsed.astimezone(UTC)

        roles_raw = payload.get("roles")
        roles: tuple[str, ...] = ()
        if isinstance(roles_raw, list | tuple | set):
            cleaned = {str(role).strip() for role in roles_raw if str(role).strip()}
            roles = tuple(sorted(cleaned))
        elif isinstance(roles_raw, str):
            role = roles_raw.strip()
            if role:
                roles = (role,)

        email = payload.get("account") or payload.get("email")
        account_email = str(email).strip() if email else None

        device_token = payload.get("device_token")
        device_token_str = str(device_token).strip() if device_token else None

        org_id = payload.get("organization_id") or payload.get("org_id")
        organization_id = str(org_id).strip() if org_id else None
        org_name_raw = payload.get("organization_name") or payload.get("org_name")
        organization_name = str(org_name_raw).strip() if org_name_raw else None
        org_role_raw = payload.get("organization_role") or payload.get("org_role")
        organization_role = str(org_role_raw).strip() if org_role_raw else None

        org_payload = payload.get("organization")
        organizations_payload = payload.get("organizations")
        organizations: list[CloudOrganization] = []
        if isinstance(org_payload, Mapping):
            with suppress(CloudAuthError):
                organizations.append(CloudOrganization.from_payload(org_payload))
        if isinstance(organizations_payload, Mapping):
            organizations_payload = [organizations_payload]
        if isinstance(organizations_payload, list | tuple | set):
            for item in organizations_payload:
                if isinstance(item, Mapping):
                    with suppress(CloudAuthError):
                        organizations.append(CloudOrganization.from_payload(item))

        if organization_id and all(org.org_id != organization_id for org in organizations):
            organizations.append(
                CloudOrganization(
                    org_id=organization_id,
                    name=organization_name,
                    roles=(organization_role,) if organization_role else (),
                    default=True,
                )
            )
        if not organization_id and organizations:
            organization_id = organizations[0].org_id
            organization_name = organizations[0].name
            organization_role = organizations[0].roles[0] if organizations[0].roles else None
        elif organization_id and not organization_name:
            match = next((org for org in organizations if org.org_id == organization_id), None)
            if match:
                organization_name = match.name
                organization_role = match.roles[0] if match.roles else organization_role

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            tenant_id=tenant_id,
            device_token=device_token_str or None,
            account_email=account_email or None,
            roles=roles,
            organization_id=organization_id or None,
            organization_name=organization_name or None,
            organization_role=organization_role or None,
            organizations=tuple(organizations),
        )

    def to_options(self) -> dict[str, Any]:
        """Serialise the token metadata for storage in config entry options."""

        options: dict[str, Any] = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tenant_id": self.tenant_id,
            "device_token": self.device_token,
            "account_email": self.account_email,
            "roles": list(self.roles),
        }
        if self.organization_id:
            options["organization_id"] = self.organization_id
        if self.organization_name:
            options["organization_name"] = self.organization_name
        if self.organization_role:
            options["organization_role"] = self.organization_role
        if self.organizations:
            options["organizations"] = [org.to_options() for org in self.organizations]
        return options

    def is_expired(self, *, now: datetime | None = None, threshold_seconds: int = 0) -> bool:
        """Return ``True`` if the access token has expired or is close to expiry."""

        if self.expires_at is None:
            return False
        now = now or datetime.now(tz=UTC)
        return (self.expires_at - now).total_seconds() <= threshold_seconds

    def available_organizations(self) -> tuple[CloudOrganization, ...]:
        return self.organizations

    def default_organization(self) -> CloudOrganization | None:
        if not self.organizations:
            return None
        for org in self.organizations:
            if org.default or org.org_id == self.organization_id:
                return org
        return self.organizations[0]


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
    "CloudOrganization",
]
