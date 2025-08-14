import pytest


@pytest.fixture(autouse=True)
def fake_dependencies(hass):
    """Pretend required dependencies are loaded."""
    hass.config.components.add("recorder")
    hass.config.components.add("diagnostics")
