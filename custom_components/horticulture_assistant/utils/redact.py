"""Simple data redaction helpers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from homeassistant.components.diagnostics import REDACTED


def redact(data: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive *keys* hidden."""
    return {k: (REDACTED if k in keys else v) for k, v in data.items()}
