import logging
from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def initialize_media_fertilizer_logs(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> bool:
    """Create media composition and fertilizer batch logs for ``plant_id``."""
    profile_sections = {
        "media_composition_log.json": [],
        "fertilizer_batch_history.json": [],
    }
    return bool(write_profile_sections(plant_id, profile_sections, base_path, overwrite))
