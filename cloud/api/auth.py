from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
ROLE_DEVICE = "device"
ROLE_ANALYTICS = "analytics"

VALID_ROLES: set[str] = {
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_VIEWER,
    ROLE_DEVICE,
    ROLE_ANALYTICS,
}


def _normalise_roles(roles_header: str | None) -> set[str]:
    if not roles_header:
        return set()
    roles: set[str] = set()
    for chunk in roles_header.split(","):
        role = chunk.strip().lower()
        if not role:
            continue
        roles.add(role)
    return roles


@dataclass(slots=True)
class Principal:
    tenant_id: str
    roles: set[str]
    subject_id: str | None = None

    def has_any(self, *required: str) -> bool:
        if not required:
            return True
        required_set = {role.lower() for role in required}
        return any(role in self.roles for role in required_set)

    def require(self, *required: str) -> None:
        if self.has_any(*required):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_role",
                "required": sorted({role.lower() for role in required}),
                "granted": sorted(self.roles),
            },
        )


async def principal_dependency(
    tenant: str = Header(..., alias="X-Tenant-ID"),
    roles_header: str | None = Header(None, alias="X-Roles"),
    subject: str | None = Header(None, alias="X-Subject-ID"),
) -> Principal:
    tenant_id = str(tenant).strip()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_tenant", "tenant": tenant},
        )
    roles = _normalise_roles(roles_header)
    if not roles:
        roles = {ROLE_VIEWER}
    invalid = sorted(role for role in roles if role not in VALID_ROLES)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_role", "roles": invalid},
        )
    subject_id = subject.strip() if isinstance(subject, str) else subject
    return Principal(tenant_id=tenant_id, roles=roles, subject_id=subject_id)


__all__ = [
    "Principal",
    "ROLE_ADMIN",
    "ROLE_ANALYTICS",
    "ROLE_DEVICE",
    "ROLE_EDITOR",
    "ROLE_VIEWER",
    "principal_dependency",
]
