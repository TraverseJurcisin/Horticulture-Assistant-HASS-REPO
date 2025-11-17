"""Simple data redaction helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.components.diagnostics import REDACTED


def redact(data: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive *keys* hidden."""
    hidden = set(keys)
    return {k: (REDACTED if k in hidden else v) for k, v in data.items()}
