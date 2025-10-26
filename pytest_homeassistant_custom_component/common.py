"""Minimal stub implementations used in tests without external dependency."""
from __future__ import annotations

from typing import Any, Callable, Mapping
from uuid import uuid4


class MockConfigEntry:
    """Lightweight ConfigEntry used in tests."""

    def __init__(
        self,
        *,
        domain: str,
        data: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
        title: str = "Mock Title",
        entry_id: str | None = None,
        unique_id: str | None = None,
        version: int = 1,
        minor_version: int = 1,
        source: str = "user",
        pref_disable_new_entities: bool | None = None,
        pref_disable_polling: bool | None = None,
        disabled_by: str | None = None,
    ) -> None:
        self.domain = domain
        self.data = dict(data or {})
        self.options = dict(options or {})
        self.title = title
        self.entry_id = entry_id or uuid4().hex
        self.unique_id = unique_id
        self.version = version
        self.minor_version = minor_version
        self.source = source
        self.pref_disable_new_entities = pref_disable_new_entities
        self.pref_disable_polling = pref_disable_polling
        self.disabled_by = disabled_by
        self._update_listeners: list[Callable[[MockConfigEntry], None]] = []
        self.hass = None

    def add_to_hass(self, hass) -> None:
        """Register the entry with Home Assistant."""
        self.hass = hass
        hass.config_entries._entries[self.entry_id] = self

    def add_update_listener(self, listener: Callable[[MockConfigEntry], None]) -> Callable[[MockConfigEntry], None]:
        """Store update listener callbacks."""
        self._update_listeners.append(listener)
        return listener

    async def async_remove(self, hass) -> None:
        """Remove the entry from Home Assistant."""
        hass.config_entries._entries.pop(self.entry_id, None)

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation of the entry."""
        return {
            "entry_id": self.entry_id,
            "version": self.version,
            "minor_version": self.minor_version,
            "domain": self.domain,
            "title": self.title,
            "data": dict(self.data),
            "options": dict(self.options),
            "source": self.source,
            "unique_id": self.unique_id,
            "pref_disable_new_entities": self.pref_disable_new_entities,
            "pref_disable_polling": self.pref_disable_polling,
            "disabled_by": self.disabled_by,
        }


__all__ = ["MockConfigEntry"]
