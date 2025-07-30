"""Simulated sensor input for DAFE."""

from __future__ import annotations

__all__ = ["get_mock_sensor_data"]


def get_mock_sensor_data() -> dict:
    """Return mocked sensor readings for testing."""
    return {"wc": 0.42, "ec": 2.2}
