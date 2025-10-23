import pytest

from custom_components.horticulture_assistant.const import (
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_FEATURE_FLAGS,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_SYNC_ENABLED,
    FEATURE_AI_ASSIST,
    FEATURE_CLOUD_SYNC,
    FEATURE_IRRIGATION_AUTOMATION,
)
from custom_components.horticulture_assistant.entitlements import (
    FeatureUnavailableError,
    derive_entitlements,
)


def test_entitlements_from_roles_and_sync_flag():
    options = {
        CONF_CLOUD_ACCOUNT_ROLES: ["premium", "irrigation"],
        CONF_CLOUD_SYNC_ENABLED: True,
    }
    entitlements = derive_entitlements(options)
    assert entitlements.allows(FEATURE_CLOUD_SYNC)
    assert entitlements.allows(FEATURE_AI_ASSIST)
    assert entitlements.allows(FEATURE_IRRIGATION_AUTOMATION)


def test_manual_feature_override_is_respected():
    options = {CONF_CLOUD_FEATURE_FLAGS: ["custom_feature", FEATURE_IRRIGATION_AUTOMATION]}
    entitlements = derive_entitlements(options)
    assert entitlements.allows(FEATURE_IRRIGATION_AUTOMATION)
    assert "custom_feature" in entitlements.features


def test_entitlement_error_includes_roles():
    options = {
        CONF_CLOUD_ACCOUNT_ROLES: ["basic"],
        CONF_CLOUD_ORGANIZATION_ROLE: "viewer",
    }
    entitlements = derive_entitlements(options)
    with pytest.raises(FeatureUnavailableError) as err:
        entitlements.ensure(FEATURE_IRRIGATION_AUTOMATION)
    message = str(err.value)
    assert "roles" in message
    assert "viewer" in message
