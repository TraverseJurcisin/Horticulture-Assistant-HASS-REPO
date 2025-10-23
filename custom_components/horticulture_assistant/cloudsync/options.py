"""Helpers for mutating config entry options with cloud token metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
)
from .auth import CloudAuthTokens

__all__ = ["merge_cloud_tokens"]


def merge_cloud_tokens(options: Mapping[str, Any], tokens: CloudAuthTokens, *, base_url: str) -> dict[str, Any]:
    """Return updated config options with the supplied cloud token metadata."""

    opts = dict(options)
    opts[CONF_CLOUD_BASE_URL] = base_url
    opts[CONF_CLOUD_SYNC_ENABLED] = True

    tenant_id = tokens.tenant_id or opts.get(CONF_CLOUD_TENANT_ID, "")
    opts[CONF_CLOUD_TENANT_ID] = tenant_id

    if tokens.device_token:
        opts[CONF_CLOUD_DEVICE_TOKEN] = tokens.device_token
    else:
        opts.pop(CONF_CLOUD_DEVICE_TOKEN, None)

    opts[CONF_CLOUD_ACCESS_TOKEN] = tokens.access_token

    if tokens.refresh_token:
        opts[CONF_CLOUD_REFRESH_TOKEN] = tokens.refresh_token
    else:
        opts.pop(CONF_CLOUD_REFRESH_TOKEN, None)

    if tokens.expires_at:
        opts[CONF_CLOUD_TOKEN_EXPIRES_AT] = tokens.expires_at.isoformat()
    else:
        opts.pop(CONF_CLOUD_TOKEN_EXPIRES_AT, None)

    if tokens.account_email:
        opts[CONF_CLOUD_ACCOUNT_EMAIL] = tokens.account_email
    else:
        opts.pop(CONF_CLOUD_ACCOUNT_EMAIL, None)

    if tokens.roles:
        opts[CONF_CLOUD_ACCOUNT_ROLES] = list(tokens.roles)
    else:
        opts.pop(CONF_CLOUD_ACCOUNT_ROLES, None)

    available_orgs = [
        {
            "id": org.org_id,
            "name": org.name,
            "roles": list(org.roles),
            "default": org.default,
        }
        for org in tokens.available_organizations()
        if org.org_id
    ]
    if available_orgs:
        opts[CONF_CLOUD_AVAILABLE_ORGANIZATIONS] = available_orgs
    else:
        opts.pop(CONF_CLOUD_AVAILABLE_ORGANIZATIONS, None)

    selected_org = None
    if tokens.organization_id:
        selected_org = next(
            (org for org in tokens.available_organizations() if org.org_id == tokens.organization_id),
            None,
        )
    if selected_org is None:
        selected_org = tokens.default_organization()

    org_id = tokens.organization_id or (selected_org.org_id if selected_org else None)
    org_name = tokens.organization_name or (selected_org.name if selected_org else None)
    org_roles = list(selected_org.roles) if selected_org else []
    org_role = tokens.organization_role or (org_roles[0] if org_roles else None)

    if org_id:
        opts[CONF_CLOUD_ORGANIZATION_ID] = org_id
    else:
        opts.pop(CONF_CLOUD_ORGANIZATION_ID, None)

    if org_name:
        opts[CONF_CLOUD_ORGANIZATION_NAME] = org_name
    else:
        opts.pop(CONF_CLOUD_ORGANIZATION_NAME, None)

    if org_role:
        opts[CONF_CLOUD_ORGANIZATION_ROLE] = org_role
    else:
        opts.pop(CONF_CLOUD_ORGANIZATION_ROLE, None)

    return opts
