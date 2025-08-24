import logging
from pathlib import Path

try:
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - outside Home Assistant
    HomeAssistant = None

from custom_components.horticulture_assistant.utils.path_utils import plants_path

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def initialize_nutrient_logs(
    plant_id: str,
    hass: HomeAssistant | None = None,
    base_dir: str | None = None,
    overwrite: bool = False,
) -> bool:
    """Create nutrient application and fertilizer cost logs for ``plant_id``."""
    if base_dir:
        base_path = Path(base_dir)
    elif hass is not None:
        try:
            base_path = Path(plants_path(hass))
        except Exception as err:  # pragma: no cover - path resolution failure
            _LOGGER.error("Error resolving Home Assistant plants directory: %s", err)
            base_path = Path(plants_path(None))
    else:
        base_path = Path(plants_path(None))
    sections = {
        "nutrient_application_log.json": [],
        "fertilizer_cost_tracking.json": [],
    }
    return bool(write_profile_sections(plant_id, sections, base_path, overwrite))
