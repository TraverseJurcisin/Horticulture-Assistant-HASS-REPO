"""Tests for :mod:`custom_components.horticulture_assistant.utils.config_validator`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.horticulture_assistant.utils.config_validator import (
    ConfigValidator,
)


class DummyHass(SimpleNamespace):
    """Minimal Home Assistant stand-in for the validator."""

    def __init__(self) -> None:
        super().__init__(states={})


@pytest.mark.parametrize(
    "api_key, base_url, expected",
    [
        ("apikey-12345", None, []),
        ("apikey-12345", "   https://example.com  ", []),
        ("   short  ", "https://example.com", ["API key appears to be too short"]),
    ],
)
def test_validate_api_config_handles_non_string_inputs(api_key, base_url, expected) -> None:
    """The validator should normalise inputs and avoid attribute errors."""

    validator = ConfigValidator(DummyHass())

    assert validator.validate_api_config(api_key, base_url) == expected


def test_validate_api_config_rejects_missing_values() -> None:
    """Missing API key should error while the optional base URL is accepted."""

    validator = ConfigValidator(DummyHass())

    errors = validator.validate_api_config(None, None)

    assert errors == ["API key is required"]


def test_validate_api_config_rejects_invalid_custom_base_url() -> None:
    """Supplying an invalid custom base URL should raise a validation error."""

    validator = ConfigValidator(DummyHass())

    errors = validator.validate_api_config("apikey-12345", "ftp://example.com")

    assert errors == ["Base URL must start with http:// or https://"]
