"""Mock WC readings for DAFE."""

from __future__ import annotations

__all__ = ["get_current_wc"]


def get_current_wc() -> float:
    """Return the current volumetric water content (mocked)."""
    # Slightly below the plateau so ``main`` prints a sample schedule.
    return 0.40
