import pytest
from homeassistant.core import HomeAssistant
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.config_entries import ConfigEntries


@pytest.fixture
async def hass(tmp_path):
    """Create a minimal Home Assistant instance for tests."""
    hass = HomeAssistant(tmp_path)
    hass.config_entries = ConfigEntries(hass, hass.config)
    await hass.config_entries.async_initialize()
    await hass.async_start()
    yield hass
    await hass.async_stop()


@pytest.fixture(autouse=True)
def fake_dependencies(hass):
    """Pretend required dependencies are loaded."""
    hass.config.components.add("recorder")
    hass.config.components.add("diagnostics")


@pytest.fixture
def enable_custom_integrations(hass):
    """Allow loading custom_components during tests."""
    hass.data.setdefault(DATA_CUSTOM_COMPONENTS, {})
    yield
