"""Shared base classes for Horticulture Assistant entities."""

from __future__ import annotations

try:  # pragma: no cover - fallback for unit tests
    from homeassistant.helpers.entity import Entity
except (ModuleNotFoundError, ImportError, AttributeError):  # pragma: no cover - executed in stubbed env

    class Entity:  # type: ignore[too-few-public-methods]
        """Minimal Home Assistant entity stub used for local tests."""

        hass = None


from .utils.entry_helpers import (
    entry_device_identifier,
    profile_device_identifier,
    resolve_entry_device_info,
    resolve_profile_device_info,
    resolve_profile_image_url,
)


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
                if (
                    self._entry_device_name
                    and not str(payload.get("name", "")).strip()
                ):
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
