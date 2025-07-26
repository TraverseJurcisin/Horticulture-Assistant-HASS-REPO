"""Substrate property definitions for DAFE."""

from __future__ import annotations

__all__ = ["get_media_profile"]


def get_media_profile(media_name: str) -> dict | None:
    """Return a media profile dictionary or ``None`` if unknown."""
    profiles = {
        "coco_coir": {
            "porosity": 0.78,
            "fc": 0.55,
            "pwp": 0.20,
            "tortuosity": 2.3,
        }
    }
    return profiles.get(media_name)
