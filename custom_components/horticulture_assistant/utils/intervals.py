"""Interval helper utilities."""

from __future__ import annotations

from typing import Any

from ..const import DEFAULT_UPDATE_MINUTES


def _normalise_update_minutes(value: Any) -> int:
    """Return a safe update interval in minutes."""

    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_UPDATE_MINUTES

    if minutes < 1:
        return 1
    if minutes > 60:
        return 60
    return minutes


__all__ = ["_normalise_update_minutes"]
