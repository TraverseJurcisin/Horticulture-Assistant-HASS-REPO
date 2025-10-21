"""Profile utilities for Horticulture Assistant."""

from .options import options_profile_to_dataclass
from .schema import (
    Citation,
    ComputedStatSnapshot,
    FieldAnnotation,
    PlantProfile,
    ProfileContribution,
    ProfileLibrarySection,
    ProfileLocalSection,
    ResolvedTarget,
)
from .utils import (
    citations_map_to_list,
    determine_species_slug,
    ensure_sections,
    normalise_profile_payload,
    sync_general_section,
)

__all__ = [
    "Citation",
    "ComputedStatSnapshot",
    "FieldAnnotation",
    "PlantProfile",
    "ProfileContribution",
    "ProfileLibrarySection",
    "ProfileLocalSection",
    "ResolvedTarget",
    "options_profile_to_dataclass",
    "citations_map_to_list",
    "determine_species_slug",
    "ensure_sections",
    "normalise_profile_payload",
    "sync_general_section",
]
