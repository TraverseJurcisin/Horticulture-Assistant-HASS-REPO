"""Ensure the options flow factory is exposed for UI configuration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant import config_flow as cfg

DOMAIN = "horticulture_assistant"


def test_options_flow_factory_returns_options_flow(hass):
    """Verify ConfigFlow.async_get_options_flow returns the OptionsFlow instance."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    flow = cfg.ConfigFlow()
    flow.hass = hass

    options_flow = flow.async_get_options_flow(entry)

    assert isinstance(options_flow, cfg.OptionsFlow)
    assert options_flow._entry is entry
    assert getattr(options_flow, "config_entry", None) is entry
