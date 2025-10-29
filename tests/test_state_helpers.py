import types

import pytest

from custom_components.horticulture_assistant.utils import state_helpers


def test_state_helpers_import_and_get_numeric_state():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="12.5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12,5", 12.5),
        ("0,125", 0.125),
        ("1,234.5", 1234.5),
        ("1.234,5", 1234.5),
        ("12,500", 12500.0),
    ],
)
def test_get_numeric_state_handles_locale_formats(raw, expected):
    hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state=raw)))

    value = state_helpers.get_numeric_state(hass, "sensor.locale")
    assert value == pytest.approx(expected)
