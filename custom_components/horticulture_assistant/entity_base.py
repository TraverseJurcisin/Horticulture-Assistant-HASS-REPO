"""Shared base classes for Horticulture Assistant entities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

try:  # pragma: no cover - fallback for unit tests
    from homeassistant.core import callback
except (ModuleNotFoundError, ImportError, AttributeError):  # pragma: no cover - executed in stubbed env

    def callback(func):  # type: ignore[no-redef]
        """Fallback ``callback`` decorator used in tests."""

        return func


try:  # pragma: no cover - fallback for unit tests
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
except (ModuleNotFoundError, ImportError, AttributeError):  # pragma: no cover - executed in stubbed env

    def async_dispatcher_connect(*_args, **_kwargs):  # type: ignore[no-redef]
        """Return a stubbed dispatcher unsubscribe callback."""

        def _cancel() -> None:
            return None

        return _cancel


try:  # pragma: no cover - fallback for unit tests
    from homeassistant.helpers.entity import Entity
except (ModuleNotFoundError, ImportError, AttributeError):  # pragma: no cover - executed in stubbed env

    class Entity:  # type: ignore[too-few-public-methods]
        """Minimal Home Assistant entity stub used for local tests."""

        hass = None


from .const import signal_profile_contexts_updated
from .utils.entry_helpers import (
    ProfileContext,
    entry_device_identifier,
    profile_device_identifier,
    resolve_entry_device_info,
    resolve_profile_context_collection,
    resolve_profile_device_info,
    resolve_profile_image_url,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class HorticultureEntryEntity(Entity):
    """Device information for entities attached to the config entry."""

    def __init__(self, entry_id: str | None, *, default_device_name: str | None = None) -> None:
        self._entry_id = entry_id
        self._entry_device_name = default_device_name

    @property
    def device_info(self) -> dict:
        """Return metadata for the config entry's device."""

        hass = getattr(self, "hass", None)
        if hass:
            info = resolve_entry_device_info(hass, self._entry_id)
            if info:
                payload = dict(info)
                if self._entry_device_name:
                    current_name = payload.get("name")
                    if not isinstance(current_name, str) or not current_name.strip():
                        payload["name"] = self._entry_device_name
                return payload

        identifier = entry_device_identifier(self._entry_id)
        name = self._entry_device_name or f"Horticulture Assistant {self._entry_id or 'entry'}"
        return {
            "identifiers": {identifier},
            "manufacturer": "Horticulture Assistant",
            "model": "Horticulture Assistant",
            "name": name,
        }


class HorticultureBaseEntity(Entity):
    """Common device information for sensors, binary sensors and switches."""

    def __init__(
        self,
        entry_id: str | None,
        plant_name: str,
        plant_id: str,
        *,
        model: str = "AI Monitored Plant",
    ) -> None:
        self._entry_id = entry_id
        self._plant_name = plant_name
        self._plant_id = plant_id
        self._model = model
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict:
        """Return device information shared across entity types."""
        if getattr(self, "hass", None):
            info = resolve_profile_device_info(self.hass, self._entry_id, self._plant_id)
            if info:
                return dict(info)

        profile_identifier = profile_device_identifier(self._entry_id, self._plant_id)
        info = {
            "identifiers": {profile_identifier},
            "name": self._plant_name,
            "manufacturer": "Horticulture Assistant",
            "model": self._model,
        }
        if self._entry_id:
            info["via_device"] = entry_device_identifier(self._entry_id)
        return info

    @property
    def entity_picture(self) -> str | None:
        """Return a profile image if configured."""
        if not self.hass:
            return None
        return resolve_profile_image_url(self.hass, self._entry_id, self._plant_id)


class ProfileContextEntityMixin:
    """Mixin that keeps entities in sync with profile context updates."""

    _context: ProfileContext | None
    _context_available: bool

    if TYPE_CHECKING:
        hass: HomeAssistant
        _entry: ConfigEntry
        _context_id: str
        _context_remove: Callable[[], None] | None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._context = context
        self._context_id = context.id
        self._context_available = True
        self._context_remove = None

    async def async_added_to_hass(self) -> None:  # pragma: no cover - exercised indirectly
        await super().async_added_to_hass()
        remove = async_dispatcher_connect(
            self.hass,
            signal_profile_contexts_updated(self._entry.entry_id),
            self._async_handle_profile_context_change,
        )
        self._context_remove = remove
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._dispose_context_listener)

    def _dispose_context_listener(self) -> None:
        """Detach from dispatcher updates when the entity is removed."""

        remove = self._context_remove
        self._context_remove = None
        if callable(remove):
            remove()

    @callback
    def _async_handle_profile_context_change(self, change: Mapping[str, Iterable[str]] | None) -> None:
        """React to dispatcher updates for the tracked profile context."""

        if not isinstance(change, Mapping):
            return
        context_id = self._context_id
        removed_ids = {str(pid) for pid in change.get("removed", ())}
        if context_id in removed_ids:
            self._handle_context_removed()
            return
        updated_ids = {str(pid) for pid in change.get("updated", ())}
        added_ids = {str(pid) for pid in change.get("added", ())}
        if context_id not in updated_ids and context_id not in added_ids:
            return
        collection = resolve_profile_context_collection(self.hass, self._entry)
        context = collection.contexts.get(context_id)
        if context is None:
            self._handle_context_removed()
            return
        self._handle_context_updated(context)

    def _handle_context_updated(self, context: ProfileContext) -> None:
        """Store the refreshed context data."""

        self._context = context
        self._context_available = True

    def _handle_context_removed(self) -> None:
        """Mark the entity unavailable when the context disappears."""

        self._context = None
        self._context_available = False
        if hasattr(self, "_attr_available"):
            self._attr_available = False  # type: ignore[assignment]
        if hasattr(self, "async_write_ha_state") and getattr(self, "hass", None):
            self.async_write_ha_state()
