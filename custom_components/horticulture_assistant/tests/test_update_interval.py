"""Tests for update interval normalisation."""

from types import SimpleNamespace

from custom_components.horticulture_assistant import _normalise_update_minutes
from custom_components.horticulture_assistant.const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_MINUTES,
)
from custom_components.horticulture_assistant.coordinator import HorticultureCoordinator


def test_normalise_update_interval_invalid_fallback() -> None:
    """Invalid values should fall back to the default."""

    assert _normalise_update_minutes(None) == DEFAULT_UPDATE_MINUTES
    assert _normalise_update_minutes("invalid") == DEFAULT_UPDATE_MINUTES


def test_normalise_update_interval_bounds() -> None:
    """Update interval is clamped to safe bounds."""

    assert _normalise_update_minutes(0) == 1
    assert _normalise_update_minutes(-5) == 1
    assert _normalise_update_minutes(1) == 1
    assert _normalise_update_minutes(30) == 30
    assert _normalise_update_minutes(120) == 60


def _mock_entry(options: dict | None = None, data: dict | None = None):
    return SimpleNamespace(options=options or {}, data=data or {})


def test_coordinator_resolves_normalised_interval_from_options() -> None:
    """Coordinator interval resolution normalises stored values."""

    entry = _mock_entry({CONF_UPDATE_INTERVAL: 0})
    assert HorticultureCoordinator._resolve_interval(entry) == 1

    entry_high = _mock_entry({CONF_UPDATE_INTERVAL: 600})
    assert HorticultureCoordinator._resolve_interval(entry_high) == 60

    entry_invalid = _mock_entry({CONF_UPDATE_INTERVAL: "not-a-number"})
    assert HorticultureCoordinator._resolve_interval(entry_invalid) == DEFAULT_UPDATE_MINUTES
