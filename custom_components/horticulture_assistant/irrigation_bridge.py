"""Simple adapters for irrigation providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:  # pragma: no cover - fallback for unit tests without Home Assistant
    from homeassistant.components.sensor import SensorEntity, SensorStateClass
except ModuleNotFoundError:  # pragma: no cover - executed in local test stubs
    from enum import Enum

    class SensorEntity:  # type: ignore[too-few-public-methods]
        """Minimal stand-in used in unit tests."""

    class SensorStateClass(str, Enum):
        MEASUREMENT = "measurement"


from homeassistant.config_entries import ConfigEntry

try:  # pragma: no cover - fallback for unit tests
    from homeassistant.core import HomeAssistant, callback
except ImportError:  # pragma: no cover - executed in stubbed test env
    HomeAssistant = Any  # type: ignore[assignment]

    def callback(func: Callable[..., Any], /) -> Callable[..., Any]:
        return func


try:  # pragma: no cover - fallback for tests without HA
    from homeassistant.helpers.event import async_track_state_change_event
except ModuleNotFoundError:  # pragma: no cover - executed in stubbed env

    async def async_track_state_change_event(*_args, **_kwargs):
        return None


from .const import DOMAIN
from .entity_base import HorticultureBaseEntity, ProfileContextEntityMixin
from .utils.entry_helpers import ProfileContext


async def async_apply_irrigation(
    hass: HomeAssistant,
    provider: str,
    zone: str | None,
    seconds: float,
) -> None:
    """Apply an irrigation run time using the selected provider.

    provider -- either ``irrigation_unlimited`` or ``opensprinkler``.
    zone -- zone/station identifier required by the provider.
    seconds -- run time in seconds.
    """
    if provider == "irrigation_unlimited":
        await hass.services.async_call(
            "irrigation_unlimited",
            "run_zone",
            {"zone_id": zone, "time": float(seconds)},
            blocking=True,
        )
        return
    if provider == "opensprinkler":
        await hass.services.async_call(
            "opensprinkler",
            "run_once",
            {"station": zone, "duration": float(seconds)},
            blocking=True,
        )
        return
    raise ValueError(f"unknown provider {provider}")


class PlantIrrigationRecommendationSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Expose Smart Irrigation runtime recommendation."""

    _attr_name = "Recommended Irrigation"
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.id}_irrigation_rec"
        self._src = self._resolve_source(context)
        self._value: float | None = None
        self._state_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_state)
        self._subscribe_source(self._context)

    @callback
    def _on_state(self, _event) -> None:
        if not self._src:
            self._value = None
        else:
            state = self.hass.states.get(self._src)
            try:
                self._value = float(state.state) if state else None
            except (TypeError, ValueError):
                self._value = None
        self.async_write_ha_state()

    def _unsubscribe_state(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None

    def _resolve_source(self, context: ProfileContext | None) -> str | None:
        if context is not None:
            source = context.first_sensor("smart_irrigation")
            if isinstance(source, str) and source:
                return source
        options = getattr(self._entry, "options", {})
        candidate = options.get("sensors") if isinstance(options, dict) else None
        if isinstance(candidate, dict):
            source = candidate.get("smart_irrigation")
            if isinstance(source, str) and source:
                return source
        return None

    def _subscribe_source(self, context: ProfileContext | None) -> None:
        self._unsubscribe_state()
        self._src = self._resolve_source(context)
        if self._src:
            self._state_unsub = async_track_state_change_event(
                self.hass,
                [self._src],
                self._on_state,
            )
            self._on_state(None)
        else:
            self._value = None
            if getattr(self, "hass", None):
                self.async_write_ha_state()

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_source(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_state()
        self._src = None
        self._value = None
        super()._handle_context_removed()
