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
    from homeassistant.helpers.device_registry import DeviceInfo
except (ModuleNotFoundError, ImportError, AttributeError):  # pragma: no cover - executed in stubbed env

    class DeviceInfo(dict):  # type: ignore[misc,too-many-ancestors]
        """Minimal stand-in for Home Assistant's DeviceInfo in tests."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)


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
        identifier = entry_device_identifier(entry_id)
        name = self._entry_device_name or f"Horticulture Assistant {entry_id or 'entry'}"
        self._attr_device_info = DeviceInfo(
            identifiers={identifier},
            manufacturer="Horticulture Assistant",
            model="Horticulture Assistant",
            name=name,
        )

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
                return DeviceInfo(**payload)

        return self._attr_device_info


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
        identifier = profile_device_identifier(entry_id, plant_id)
        self._attr_device_info = DeviceInfo(
            identifiers={identifier},
            name=self._plant_name,
            manufacturer="Horticulture Assistant",
        )

    @property
    def profile_id(self) -> str:
        """Return the unique profile identifier associated with this entity."""

        return self._plant_id

    @property
    def profile_name(self) -> str:
        """Return the current profile display name for this entity."""

        return self._plant_name

    @property
    def device_info(self) -> dict:
        """Return device information shared across entity types."""
        name = self.profile_name
        if getattr(self, "hass", None):
            info = resolve_profile_device_info(self.hass, self._entry_id, self._plant_id)
            if info:
                name = info.get("name") or name

        return {
            "identifiers": {profile_device_identifier(self._entry_id, self.profile_id)},
            "name": name,
            "manufacturer": "Horticulture Assistant",
        }

    @property
    def entity_picture(self) -> str | None:
        """Return a profile image if configured."""
        if not self.hass:
            return None
        return resolve_profile_image_url(self.hass, self._entry_id, self._plant_id)

    def profile_unique_id(self, key: str | None = None) -> str:
        """Return a stable unique id for profile entities scoped to the entry."""

        entry_part = str(self._entry_id) if self._entry_id is not None else "entry"
        profile_part = self.profile_id or "profile"
        if key:
            return f"{entry_part}_{profile_part}_{key}"
        return f"{entry_part}_{profile_part}"


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
        self._context_id = context.profile_id
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
        if hasattr(self, "_plant_name"):
            self._plant_name = context.name

    def _handle_context_removed(self) -> None:
        """Clear cached context data when the profile disappears."""

        self._context = None
        self._context_available = False
        if hasattr(self, "async_write_ha_state") and getattr(self, "hass", None):
            self.async_write_ha_state()
