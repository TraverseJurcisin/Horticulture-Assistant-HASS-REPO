"""In-memory registry for managing plant profiles.

This module centralizes profile operations such as loading from storage,
updating sensors, refreshing species data and exporting the profile
collection.  Having a registry makes it easier for services and diagnostics
modules to reason about the set of configured plants without each feature
needing to parse config entry options or storage files individually.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PROFILES
from .profile import store as profile_store
from .profile.schema import PlantProfile


class ProfileRegistry:
    """Maintain a collection of plant profiles for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._profiles: dict[str, PlantProfile] = {}

    # ---------------------------------------------------------------------
    # Initialization and access helpers
    # ---------------------------------------------------------------------
    async def async_initialize(self) -> None:
        """Load profiles from storage and config entry options."""

        stored = await profile_store.async_load_profiles(self.hass)
        self._profiles.update(stored)

        # Merge in any profiles referenced only in config entry options.
        for pid, data in self.entry.options.get(CONF_PROFILES, {}).items():
            prof = self._profiles.get(pid)
            if prof:
                prof.display_name = data.get("name", prof.display_name)
                if sensors := data.get("sensors"):
                    prof.general.setdefault("sensors", sensors)
                continue
            self._profiles[pid] = PlantProfile(
                plant_id=pid,
                display_name=data.get("name", pid),
                species=data.get("species"),
            )

    def list_profiles(self) -> list[PlantProfile]:
        """Return all known profiles."""

        return list(self._profiles.values())

    def get(self, plant_id: str) -> PlantProfile | None:
        """Return a specific profile by id."""

        return self._profiles.get(plant_id)

    # ---------------------------------------------------------------------
    # Mutation helpers
    # ---------------------------------------------------------------------
    async def async_replace_sensor(
        self, profile_id: str, measurement: str, entity_id: str
    ) -> None:
        """Update a profile's bound sensor entity.

        This mirrors the behaviour of the ``replace_sensor`` service but
        allows tests and other components to call the logic directly.
        """

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")
        sensors = dict(profile.get("sensors", {}))
        sensors[measurement] = entity_id
        profile["sensors"] = sensors
        profiles[profile_id] = profile
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        # Update config entry and keep local copy in sync for tests.
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        # Mirror changes into in-memory structure if profile exists.
        if prof_obj := self._profiles.get(profile_id):
            prof_obj.general.setdefault("sensors", {})[measurement] = entity_id

    async def async_refresh_species(self, profile_id: str) -> None:
        """Placeholder for species refresh logic.

        The real integration refreshes thresholds from OpenPlantbook or other
        sources.  For the lightweight registry we simply mark the profile as
        refreshed, leaving the heavy lifting to the coordinators.
        """

        prof = self._profiles.get(profile_id)
        if not prof:
            raise ValueError(f"unknown profile {profile_id}")
        prof.last_resolved = "1970-01-01T00:00:00Z"
        await profile_store.async_save_profile(self.hass, prof)

    async def async_export(self, path: str | Path) -> Path:
        """Export all profiles to a JSON file and return the path."""

        p = Path(path)
        if not p.is_absolute():
            p = Path(self.hass.config.path(p))  # type: ignore[attr-defined]
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [p_.to_json() for p_ in self._profiles.values()]
        with p.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
        return p

    # ------------------------------------------------------------------
    # Utility helpers primarily for diagnostics
    # ------------------------------------------------------------------
    def summaries(self) -> list[dict[str, Any]]:
        """Return a serialisable summary of all profiles."""

        return [p.summary() for p in self._profiles.values()]

    def __iter__(self) -> Iterable[PlantProfile]:
        return iter(self._profiles.values())

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._profiles)
