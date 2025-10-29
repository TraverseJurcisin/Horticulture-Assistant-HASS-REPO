import types

from custom_components.horticulture_assistant.utils import state_helpers


def test_state_helpers_import_and_get_numeric_state():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="12.5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5


def test_get_numeric_state_supports_decimal_comma():
    hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="5,5")))

    value = state_helpers.get_numeric_state(hass, "sensor.decimal")
    assert value == 5.5


def test_get_numeric_state_handles_thousand_and_decimal_separators():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="1.234,5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.locale")
    assert value == 1234.5
