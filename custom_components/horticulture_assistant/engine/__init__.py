"""Engine subpackage for Horticulture Assistant.

Provides convenient access to bundled agronomy helpers.  The heavy
``plant_engine`` package lives one level deeper, but we surface commonly
used modules like :mod:`guidelines` for internal callers.
"""

from .plant_engine import guidelines  # noqa: F401

__all__ = ["guidelines"]
