"""Profile utilities for Horticulture Assistant."""

from .options import options_profile_to_dataclass
from .schema import (
    Citation,
    ComputedStatSnapshot,
    FieldAnnotation,
    BioProfile,
    CultivarProfile,
    HarvestEvent,
    ProfileContribution,
    ProfileLibrarySection,
    ProfileLocalSection,
    ProfileSections,
    ResolvedTarget,
    RunEvent,
    SpeciesProfile,
    YieldStatistic,
)
from .utils import (
    citations_map_to_list,
    determine_species_slug,
    ensure_sections,
    link_species_and_cultivars,
    normalise_profile_payload,
    sync_general_section,
)

__all__ = [
    "Citation",
    "ComputedStatSnapshot",
    "FieldAnnotation",
    "BioProfile",
    "CultivarProfile",
    "HarvestEvent",
    "ProfileContribution",
    "ProfileLibrarySection",
    "ProfileLocalSection",
    "ProfileSections",
    "ResolvedTarget",
    "RunEvent",
    "SpeciesProfile",
    "YieldStatistic",
    "options_profile_to_dataclass",
    "citations_map_to_list",
    "determine_species_slug",
    "ensure_sections",
    "link_species_and_cultivars",
    "normalise_profile_payload",
    "sync_general_section",
]
