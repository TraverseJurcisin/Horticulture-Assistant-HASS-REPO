"""Mock EC readings for DAFE."""

from __future__ import annotations

__all__ = ["get_current_ec"]


def get_current_ec() -> float:
    """Return the current root-zone EC in mS/cm (mocked)."""
    return 2.2
