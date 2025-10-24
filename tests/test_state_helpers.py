import types

from custom_components.horticulture_assistant.utils import state_helpers


def _make_hass(value: str):
    return types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state=value))
    )


def test_state_helpers_import_and_get_numeric_state():
    hass = _make_hass("12.5")
    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5


def test_get_numeric_state_strips_units():
    hass = _make_hass("7.5 pH")
    value = state_helpers.get_numeric_state(hass, "sensor.ph")
    assert value == 7.5


def test_get_numeric_state_rejects_nan():
    hass = _make_hass("nan")
    assert state_helpers.get_numeric_state(hass, "sensor.nan") is None
