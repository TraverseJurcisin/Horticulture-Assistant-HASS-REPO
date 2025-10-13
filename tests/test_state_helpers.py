import types

from custom_components.horticulture_assistant.utils import state_helpers


def test_state_helpers_import_and_get_numeric_state():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="12.5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5
