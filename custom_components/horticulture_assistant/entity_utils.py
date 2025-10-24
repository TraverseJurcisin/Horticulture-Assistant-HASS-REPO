from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - fallback for tests without Home Assistant
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env
    HomeAssistant = Any  # type: ignore[assignment]

try:  # pragma: no cover - fallback for tests
    from homeassistant.helpers import issue_registry as ir
except (ModuleNotFoundError, ImportError):  # pragma: no cover - executed in stubbed env
    import types
    from enum import Enum

    class IssueSeverity(str, Enum):
        WARNING = "warning"

    ir = types.SimpleNamespace(  # type: ignore[assignment]
        IssueSeverity=IssueSeverity,
        async_create_issue=lambda *_args, **_kwargs: None,
    )

from .const import DOMAIN


def ensure_entities_exist(
    hass: HomeAssistant,
    plant_id: str,
    entity_ids: Iterable[str],
    *,
    translation_key: str = "missing_entity",
    placeholders: dict[str, str] | None = None,
) -> None:
    """Create a repairs issue when referenced entities are missing."""
    missing = [eid for eid in entity_ids if eid and hass.states.get(eid) is None]
    if not missing:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"missing_entity_{plant_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders or {"plant_id": plant_id},
    )
