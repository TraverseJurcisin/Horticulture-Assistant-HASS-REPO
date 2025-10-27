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
    "raw, expected",
    [
        ("21,5", 21.5),
        ("1.234,56", 1234.56),
        ("1 234,56", 1234.56),
    ],
)
def test_get_numeric_state_handles_locale_formats(raw, expected):
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state=raw))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.temp")
    assert value == pytest.approx(expected)
