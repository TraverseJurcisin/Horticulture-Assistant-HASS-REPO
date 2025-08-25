from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import CONF_PROFILES, DOMAIN
from .derived import _svp_kpa, dew_point_c

_LOGGER = logging.getLogger(__name__)


class HorticultureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data coordinator for plant profile metrics."""

    def __init__(self, hass: HomeAssistant, entry_id: str, options: dict[str, Any]) -> None:
        self._entry_id = entry_id
        self._options = options

        interval = int(options.get("update_interval", 5))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry_id}",
            update_interval=timedelta(minutes=interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            profiles: dict[str, Any] = self._options.get(CONF_PROFILES, {})
            data: dict[str, Any] = {"profiles": {}}
            for pid, profile in profiles.items():
                metrics = await self._compute_metrics(pid, profile)
                data["profiles"][pid] = {
                    "name": profile.get("name"),
                    "metrics": metrics,
                }
            return data
        except Exception as err:  # pragma: no cover - simple stub
            raise UpdateFailed(str(err)) from err

    async def _compute_metrics(self, profile_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Compute metrics for a profile.

        Currently only derives a rudimentary Daily Light Integral (DLI) based on the
        configured illuminance sensor. The conversion factor is not intended to be
        scientifically accurate but provides deterministic behaviour for testing.
        """

        sensors: dict[str, Any] = profile.get("sensors", {})
        illuminance = sensors.get("illuminance")
        temperature = sensors.get("temperature")
        humidity = sensors.get("humidity")
        dli: float | None = None
        vpd: float | None = None
        dew_point: float | None = None

        if illuminance:
            state = self.hass.states.get(illuminance)
            if state is not None and state.state not in {"unknown", "unavailable"}:
                try:
                    lux = float(state.state)
                except (TypeError, ValueError):
                    lux = None
                if lux is not None:
                    # Simple placeholder conversion from lux to DLI.
                    dli = lux * 1e-5

        t_c: float | None = None
        if temperature:
            t_state = self.hass.states.get(temperature)
            if t_state is not None and t_state.state not in {"unknown", "unavailable"}:
                try:
                    t = float(t_state.state)
                except (TypeError, ValueError):
                    t = None
                if t is not None:
                    unit = t_state.attributes.get("unit_of_measurement")
                    if unit == UnitOfTemperature.FAHRENHEIT:
                        t = TemperatureConverter.convert(
                            t, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
                        )
                    t_c = t

        h: float | None = None
        if humidity:
            h_state = self.hass.states.get(humidity)
            if h_state is not None and h_state.state not in {"unknown", "unavailable"}:
                try:
                    h = float(h_state.state)
                except (TypeError, ValueError):
                    h = None

        if t_c is not None and h is not None:
            dew_point = dew_point_c(t_c, h)
            vpd = _svp_kpa(t_c) * (1 - h / 100.0)

        return {"dli": dli, "vpd": vpd, "dew_point": dew_point}
