"""Helpers for interpreting account metadata into feature entitlements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_FEATURE_FLAGS,
    CONF_CLOUD_ORGANIZATION_ID,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_SYNC_ENABLED,
    FEATURE_ADVANCED_ANALYTICS,
    FEATURE_AI_ASSIST,
    FEATURE_CLOUD_SYNC,
    FEATURE_IRRIGATION_AUTOMATION,
    FEATURE_LOCAL_PROFILES,
    FEATURE_ORGANIZATION_ADMIN,
    PREMIUM_FEATURES,
)

__all__ = [
    "Entitlements",
    "FeatureUnavailableError",
    "derive_entitlements",
]


FEATURE_LABELS: dict[str, str] = {
    FEATURE_LOCAL_PROFILES: "Local profile management",
    FEATURE_CLOUD_SYNC: "Cloud sync",
    FEATURE_AI_ASSIST: "AI assistance",
    FEATURE_IRRIGATION_AUTOMATION: "Irrigation automation",
    FEATURE_ADVANCED_ANALYTICS: "Advanced analytics",
    FEATURE_ORGANIZATION_ADMIN: "Organization administration",
}

ROLE_FEATURE_MAP: dict[str, set[str]] = {
    "basic": {FEATURE_CLOUD_SYNC},
    "sync": {FEATURE_CLOUD_SYNC},
    "cloud": {FEATURE_CLOUD_SYNC},
    "ai": {FEATURE_AI_ASSIST, FEATURE_ADVANCED_ANALYTICS},
    "analytics": {FEATURE_ADVANCED_ANALYTICS},
    "premium": {
        FEATURE_CLOUD_SYNC,
        FEATURE_AI_ASSIST,
        FEATURE_IRRIGATION_AUTOMATION,
        FEATURE_ADVANCED_ANALYTICS,
    },
    "pro": {
        FEATURE_CLOUD_SYNC,
        FEATURE_AI_ASSIST,
        FEATURE_IRRIGATION_AUTOMATION,
        FEATURE_ADVANCED_ANALYTICS,
    },
    "irrigation": {FEATURE_IRRIGATION_AUTOMATION},
    "grower_plus": {FEATURE_AI_ASSIST, FEATURE_IRRIGATION_AUTOMATION},
    "org_admin": {FEATURE_ORGANIZATION_ADMIN, FEATURE_CLOUD_SYNC},
    "org_manager": {FEATURE_CLOUD_SYNC, FEATURE_ADVANCED_ANALYTICS},
}

ORG_ROLE_FEATURE_MAP: dict[str, set[str]] = {
    "admin": {FEATURE_ORGANIZATION_ADMIN, FEATURE_CLOUD_SYNC},
    "owner": {FEATURE_ORGANIZATION_ADMIN, FEATURE_CLOUD_SYNC},
    "manager": {FEATURE_CLOUD_SYNC, FEATURE_ADVANCED_ANALYTICS},
    "editor": {FEATURE_CLOUD_SYNC},
    "viewer": set(),
}


class FeatureUnavailableError(RuntimeError):
    """Raised when attempting to use a feature the account is not entitled to."""

    def __init__(self, feature: str, entitlements: Entitlements, *, reason: str) -> None:
        self.feature = feature
        self.entitlements = entitlements
        self.reason = reason
        label = FEATURE_LABELS.get(feature, feature)
        fragments = [f"{label} is not available for the current account"]
        if entitlements.roles:
            fragments.append(f"roles: {', '.join(entitlements.roles)}")
        if entitlements.organization_role:
            fragments.append(f"organization role: {entitlements.organization_role}")
        if reason == "requires_subscription":
            fragments.append("requires an active subscription")
        elif reason == "organization_role":
            fragments.append("requires an elevated organization role")
        message = "; ".join(fragments)
        super().__init__(message)


@dataclass(frozen=True)
class Entitlements:
    """Represents feature availability derived from account metadata."""

    features: frozenset[str]
    roles: tuple[str, ...]
    organization_role: str | None = None
    organization_id: str | None = None
    account_email: str | None = None
    source: str = "local"

    def allows(self, feature: str) -> bool:
        return feature in self.features

    def ensure(self, feature: str) -> None:
        if self.allows(feature):
            return
        reason = "requires_subscription"
        if feature == FEATURE_ORGANIZATION_ADMIN:
            reason = "organization_role"
        raise FeatureUnavailableError(feature, self, reason=reason)

    def to_attributes(self) -> dict[str, Any]:
        return {
            "features": sorted(self.features),
            "roles": list(self.roles),
            "organization_role": self.organization_role,
            "organization_id": self.organization_id,
            "account_email": self.account_email,
            "source": self.source,
        }


FALSE_STRINGS = {"0", "false", "no", "off"}
TRUE_STRINGS = {"1", "true", "yes", "on"}


def _coerce_bool(value: Any) -> bool:
    """Return ``value`` interpreted as a boolean flag."""

    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().casefold()
        if not text:
            return False
        if text in TRUE_STRINGS:
            return True
        if text in FALSE_STRINGS:
            return False
    return bool(value)


def _normalise_roles(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str) and raw.strip():
        return (raw.strip(),)
    if isinstance(raw, Sequence):
        values: list[str] = []
        for item in raw:
            if not item:
                continue
            values.append(str(item).strip())
        return tuple(values)
    return ()


def _feature_set_from_roles(roles: Iterable[str]) -> set[str]:
    features: set[str] = set()
    for role in roles:
        key = role.lower()
        if key in ROLE_FEATURE_MAP:
            features.update(ROLE_FEATURE_MAP[key])
        # Allow compound roles like "premium:ai"
        if ":" in key:
            parts = key.split(":")
            for part in parts:
                part = part.strip()
                if part in ROLE_FEATURE_MAP:
                    features.update(ROLE_FEATURE_MAP[part])
    return features


def derive_entitlements(options: Mapping[str, Any] | None) -> Entitlements:
    """Return :class:`Entitlements` derived from config entry options."""

    options = options or {}
    base_features: set[str] = {FEATURE_LOCAL_PROFILES}
    manual = options.get(CONF_CLOUD_FEATURE_FLAGS)
    if isinstance(manual, str) and manual.strip():
        base_features.add(manual.strip())
    elif isinstance(manual, Sequence):
        base_features.update(str(value).strip() for value in manual if value)

    roles = _normalise_roles(options.get(CONF_CLOUD_ACCOUNT_ROLES))
    base_features.update(_feature_set_from_roles(roles))

    org_role_raw = options.get(CONF_CLOUD_ORGANIZATION_ROLE)
    org_role = str(org_role_raw).strip() if org_role_raw else None
    if org_role:
        mapped = ORG_ROLE_FEATURE_MAP.get(org_role.lower())
        if mapped:
            base_features.update(mapped)

    if _coerce_bool(options.get(CONF_CLOUD_SYNC_ENABLED)):
        base_features.add(FEATURE_CLOUD_SYNC)

    account_email_raw = options.get(CONF_CLOUD_ACCOUNT_EMAIL)
    account_email = str(account_email_raw).strip() if account_email_raw else None
    organization_id_raw = options.get(CONF_CLOUD_ORGANIZATION_ID)
    organization_id = str(organization_id_raw).strip() if organization_id_raw else None

    # Remove empty markers that may have been added via manual overrides
    cleaned_features = {feature for feature in base_features if feature}

    return Entitlements(
        features=frozenset(cleaned_features),
        roles=tuple(role for role in roles if role),
        organization_role=org_role or None,
        organization_id=organization_id or None,
        account_email=account_email or None,
        source="cloud" if options.get(CONF_CLOUD_SYNC_ENABLED) else "local",
    )


def feature_is_premium(feature: str) -> bool:
    return feature in PREMIUM_FEATURES
