"""EC drift modeling utilities."""

from __future__ import annotations

__all__ = ["calculate_ec_drift"]


def calculate_ec_drift(
    ec_in: float,
    ec_out: float,
    volume_in: float,
    volume_out: float,
    volume_media: float,
) -> float:
    """Return the predicted EC change in mS/cm.

    Parameters
    ----------
    ec_in : float
        EC of the irrigation solution.
    ec_out : float
        EC of the drainage leaving the root zone.
    volume_in : float
        Irrigation volume applied (mL or any unit).
    volume_out : float
        Drainage volume leaving the substrate (same units as ``volume_in``).
    volume_media : float
        Volume of water contained in the substrate prior to irrigation.
    """
    if volume_media <= 0:
        raise ValueError("volume_media must be positive")
    if volume_in < 0 or volume_out < 0:
        raise ValueError("volumes must be non-negative")

    delta_ec = (ec_in * volume_in - ec_out * volume_out) / volume_media
    return delta_ec
