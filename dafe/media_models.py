"""Media profile definitions for the Diffusion-Aware Fertigation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

__all__ = ["MediaProfile", "get_media_profile"]


@dataclass(frozen=True, slots=True)
class MediaProfile:
    """Container object describing substrate properties."""

    name: str
    porosity: float
    fc: float
    pwp: float
    tortuosity: float


@lru_cache(maxsize=None)
def get_media_profile(media_name: str) -> MediaProfile | None:
    """Return a :class:`MediaProfile` or ``None`` if ``media_name`` unknown."""

    data = {
        "coco_coir": {
            "porosity": 0.78,
            "fc": 0.55,
            "pwp": 0.20,
            "tortuosity": 2.3,
        }
    }.get(media_name)

    if not data:
        return None

    return MediaProfile(media_name, **data)
