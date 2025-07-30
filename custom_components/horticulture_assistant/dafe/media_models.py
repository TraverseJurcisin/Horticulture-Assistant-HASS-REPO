"""Media profile definitions for the Diffusion-Aware Fertigation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from plant_engine.utils import load_dataset

# Dataset file residing under ``data/`` used to populate media properties.
DATA_FILE = "media/dafe_media_profiles.json"

__all__ = ["MediaProfile", "get_media_profile"]


@dataclass(frozen=True, slots=True)
class MediaProfile:
    """Container object describing substrate properties."""

    name: str
    porosity: float
    fc: float
    pwp: float
    tortuosity: float


def _profile_data() -> dict:
    """Return cached media profile data from :data:`DATA_FILE`."""

    return load_dataset(DATA_FILE)


@lru_cache(maxsize=None)
def get_media_profile(media_name: str) -> MediaProfile | None:
    """Return a :class:`MediaProfile` for ``media_name`` if available."""

    data = _profile_data().get(media_name)
    if not data:
        return None
    return MediaProfile(media_name, **data)
