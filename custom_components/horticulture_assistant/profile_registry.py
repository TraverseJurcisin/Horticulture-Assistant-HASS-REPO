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
from copy import deepcopy
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify

from .const import (
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    PROFILE_SCOPE_CHOICES,
    PROFILE_SCOPE_DEFAULT,
)
from .profile.schema import PlantProfile

STORAGE_VERSION = 2
STORAGE_KEY = "horticulture_assistant_profiles"


class ProfileRegistry:
    """Maintain a collection of plant profiles for the integration."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._profiles: dict[str, PlantProfile] = {}

    # ---------------------------------------------------------------------
    # Initialization and access helpers
    # ---------------------------------------------------------------------
    async def async_load(self) -> None:
        """Load profiles from storage and config entry options."""

        data = await self._store.async_load() or {}

        # Older versions stored profiles as a list; convert to the new mapping
        # structure keyed by ``plant_id``.
        if isinstance(data, list):  # pragma: no cover - legacy format
            data = {"profiles": {p["plant_id"]: p for p in data if "plant_id" in p}}

        profiles = data.get("profiles", {})
        self._profiles = {pid: PlantProfile.from_json(p) for pid, p in profiles.items()}

        # Merge in any profiles referenced only in config entry options.
        for pid, data in self.entry.options.get(CONF_PROFILES, {}).items():
            prof = self._profiles.get(pid)
            scope = data.get(CONF_PROFILE_SCOPE, data.get("scope"))
            if prof:
                prof.display_name = data.get("name", prof.display_name)
                if sensors := data.get("sensors"):
                    prof.general.setdefault("sensors", sensors)
                if scope:
                    prof.general[CONF_PROFILE_SCOPE] = scope
                elif CONF_PROFILE_SCOPE not in prof.general:
                    prof.general[CONF_PROFILE_SCOPE] = PROFILE_SCOPE_DEFAULT
                continue
            prof_obj = PlantProfile(
                plant_id=pid,
                display_name=data.get("name", pid),
                species=data.get("species"),
            )
            if sensors := data.get("sensors"):
                prof_obj.general.setdefault("sensors", sensors)
            if scope:
                prof_obj.general[CONF_PROFILE_SCOPE] = scope
            self._profiles[pid] = prof_obj

        for profile in self._profiles.values():
            profile.general.setdefault(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)

    async def async_save(self) -> None:
        await self._store.async_save({"profiles": {pid: prof.to_json() for pid, prof in self._profiles.items()}})

    # Backwards compatibility for previous method name
    async_initialize = async_load

    def list_profiles(self) -> list[PlantProfile]:
        """Return all known profiles."""

        return list(self._profiles.values())

    def iter_profiles(self) -> list[PlantProfile]:
        return self.list_profiles()

    def get_profile(self, plant_id: str) -> PlantProfile | None:
        """Return a specific profile by id."""

        return self._profiles.get(plant_id)

    # Backwards compatibility for existing tests
    get = get_profile

    # ---------------------------------------------------------------------
    # Mutation helpers
    # ---------------------------------------------------------------------
    async def async_replace_sensor(self, profile_id: str, measurement: str, entity_id: str) -> None:
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
        await self.async_save()

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
        await self.async_save()

    async def async_export(self, path: str | Path) -> Path:
        """Export all profiles to a JSON file and return the path."""

        p = Path(path)
        if not p.is_absolute():
            p = Path(self.hass.config.path(str(p)))  # type: ignore[attr-defined]
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [p_.to_json() for p_ in self._profiles.values()]
        with p.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
        return p

    async def async_add_profile(
        self,
        name: str,
        base_id: str | None = None,
        scope: str | None = None,
    ) -> str:
        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        base = slugify(name) or "profile"
        candidate = base
        idx = 1
        while candidate in profiles or candidate in self._profiles:
            idx += 1
            candidate = f"{base}_{idx}"

        new_profile: dict[str, Any] = {"name": name}
        if base_id:
            source = profiles.get(base_id)
            if source is None:
                raise ValueError(f"unknown profile {base_id}")
            new_profile = deepcopy(source)
            new_profile["name"] = name
            if scope is None:
                scope = source.get(CONF_PROFILE_SCOPE, source.get("scope"))

        resolved_scope = scope or PROFILE_SCOPE_DEFAULT
        if resolved_scope not in PROFILE_SCOPE_CHOICES:
            raise ValueError(f"invalid scope {resolved_scope}")
        new_profile[CONF_PROFILE_SCOPE] = resolved_scope
        new_profile.pop("scope", None)

        profiles[candidate] = new_profile
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts

        prof_obj = PlantProfile(
            plant_id=candidate,
            display_name=name,
            species=new_profile.get("species"),
        )
        if sensors := new_profile.get("sensors"):
            prof_obj.general.setdefault("sensors", sensors)
        prof_obj.general[CONF_PROFILE_SCOPE] = resolved_scope
        self._profiles[candidate] = prof_obj
        await self.async_save()
        return candidate

    async def async_duplicate_profile(self, source_id: str, new_name: str) -> str:
        """Duplicate ``source_id`` into a new profile with ``new_name``."""

        return await self.async_add_profile(new_name, base_id=source_id)

    async def async_delete_profile(self, profile_id: str) -> None:
        """Remove ``profile_id`` from the registry and storage."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        if profile_id not in profiles:
            raise ValueError(f"unknown profile {profile_id}")
        profiles.pop(profile_id)
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts
        self._profiles.pop(profile_id, None)
        await self.async_save()

    async def async_link_sensors(self, profile_id: str, sensors: dict[str, str]) -> None:
        """Link multiple sensor entities to ``profile_id``."""

        profiles = dict(self.entry.options.get(CONF_PROFILES, {}))
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"unknown profile {profile_id}")
        prof = dict(profile)
        prof["sensors"] = sensors
        profiles[profile_id] = prof
        new_opts = dict(self.entry.options)
        new_opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        self.entry.options = new_opts
        if prof_obj := self._profiles.get(profile_id):
            prof_obj.general["sensors"] = sensors
        await self.async_save()

    async def async_import_template(self, template: str, name: str | None = None) -> str:
        """Create a profile from a bundled template.

        Templates are stored under ``data/templates/<template>.json`` and
        contain a serialised :class:`PlantProfile`.  The new profile will copy
        variables and metadata from the template while generating a unique
        identifier based on ``name`` or the template's display name.
        """

        template_path = Path(__file__).parent / "data" / "templates" / f"{template}.json"
        if not template_path.exists():
            raise ValueError(f"unknown template {template}")

        text = template_path.read_text(encoding="utf-8")
        data = json.loads(text)
        prof = PlantProfile.from_json(data)
        scope = (prof.general or {}).get(CONF_PROFILE_SCOPE)
        pid = await self.async_add_profile(name or prof.display_name, scope=scope)
        new_prof = self._profiles[pid]
        new_prof.species = prof.species
        new_prof.variables = prof.variables
        new_prof.general.update(prof.general)
        new_prof.general.setdefault(CONF_PROFILE_SCOPE, scope or PROFILE_SCOPE_DEFAULT)
        new_prof.citations = prof.citations
        await self.async_save()
        return pid

    async def async_export_profile(self, profile_id: str, path: str | Path) -> Path:
        """Export a single profile to ``path`` and return it."""

        from .profile.export import async_export_profile

        return await async_export_profile(self.hass, profile_id, path)

    async def async_import_profiles(self, path: str | Path) -> int:
        """Import profiles from ``path`` and reload the registry."""

        from .profile.importer import async_import_profiles

        count = await async_import_profiles(self.hass, path)
        await self.async_load()
        return count

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
