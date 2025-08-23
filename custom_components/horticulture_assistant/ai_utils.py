from __future__ import annotations

import re


def extract_numbers(text: str) -> list[float]:
    """Return sorted list of plausible floats extracted from text."""
    seen: set[float] = set()
    for match in re.findall(r"[-+]?\d*\.?\d+", text):
        try:
            val = float(match)
        except ValueError:
            continue
        if -273.15 <= val <= 1000:
            seen.add(val)
    return sorted(seen)
