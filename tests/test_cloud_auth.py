from __future__ import annotations

import pytest
from cloud.api.auth import principal_dependency
from fastapi import HTTPException, status


@pytest.mark.asyncio
async def test_principal_dependency_normalises_input() -> None:
    principal = await principal_dependency(
        tenant="  DemoTenant ",
        roles_header="Admin, viewer ,ADMIN",
        subject="  device-01  ",
    )
    assert principal.tenant_id == "DemoTenant"
    assert principal.roles == {"admin", "viewer"}
    assert principal.subject_id == "device-01"


@pytest.mark.asyncio
async def test_principal_dependency_rejects_invalid_role() -> None:
    with pytest.raises(HTTPException) as exc:
        await principal_dependency(
            tenant="TenantA",
            roles_header="admin,invalid",
            subject=None,
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == {"error": "invalid_role", "roles": ["invalid"]}


@pytest.mark.asyncio
async def test_principal_dependency_requires_tenant() -> None:
    with pytest.raises(HTTPException) as exc:
        await principal_dependency(
            tenant="   ",
            roles_header=None,
            subject=None,
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail["error"] == "invalid_tenant"
