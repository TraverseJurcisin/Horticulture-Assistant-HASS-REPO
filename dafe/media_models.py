"""Substrate property definitions for DAFE.

Media profiles are represented as dataclasses so attribute access is explicit
and type checked. Only a single example profile is included to keep the test
suite lightweight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["MediaProfile", "get_media_profile"]


@dataclass(frozen=True)
class MediaProfile:
    """Physical parameters of a growing media."""

    porosity: float
    fc: float
    pwp: float
    tortuosity: float


_PROFILES = {
    "coco_coir": {
        "porosity": 0.78,
        "fc": 0.55,
        "pwp": 0.20,
        "tortuosity": 2.3,
    }
}


def get_media_profile(media_name: str) -> Optional[MediaProfile]:
    """Return a :class:`MediaProfile` or ``None`` if ``media_name`` unknown."""

    data = _PROFILES.get(media_name)
    return MediaProfile(**data) if data else None
