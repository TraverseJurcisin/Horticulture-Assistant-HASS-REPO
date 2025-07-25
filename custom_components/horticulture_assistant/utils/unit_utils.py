"""Shared unit conversion helpers for Horticulture Assistant."""

from __future__ import annotations

UNIT_CONVERSIONS = {
    "kg": 1.0,
    "g": 0.001,
    "lb": 0.453592,
    "oz": 0.0283495,
    "L": 1.0,
    "mL": 0.001,
    "gal": 3.78541,
    "fl_oz": 0.0295735,
}

PAIR_CONVERSIONS = {
    ("oz", "g"): 28.3495,
    ("g", "oz"): 1 / 28.3495,
    ("mL", "L"): 0.001,
    ("L", "mL"): 1000,
    ("gal", "L"): 3.78541,
    ("L", "gal"): 1 / 3.78541,
}


def to_base(value: float, unit: str) -> float:
    """Return ``value`` converted to kilograms or liters."""
    if unit not in UNIT_CONVERSIONS:
        raise ValueError(f"Unsupported unit: {unit}")
    return value * UNIT_CONVERSIONS[unit]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert ``value`` between supported units."""
    if from_unit == to_unit:
        return value
    key = (from_unit, to_unit)
    if key in PAIR_CONVERSIONS:
        return value * PAIR_CONVERSIONS[key]
    if from_unit in UNIT_CONVERSIONS and to_unit in UNIT_CONVERSIONS:
        return value * UNIT_CONVERSIONS[from_unit] / UNIT_CONVERSIONS[to_unit]
    raise ValueError(f"Unsupported conversion: {from_unit} -> {to_unit}")
