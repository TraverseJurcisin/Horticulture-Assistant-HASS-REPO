from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import CONF_PROFILE_SCOPE
from .profile.schema import BioProfile
from .profile.utils import normalise_profile_payload

LOCAL_RELATIVE_PATH = "custom_components/horticulture_assistant/data/local"
PROFILES_DIRNAME = "profiles"


def _slug_source(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _mutable_copy(value: Any) -> Any:
    """Return a deepcopy-friendly clone with immutable mappings converted."""

    if isinstance(value, Mapping):
        return {str(key): _mutable_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mutable_copy(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mutable_copy(item) for item in value)
    if isinstance(value, set):
        return {_mutable_copy(item) for item in value}
    return deepcopy(value)


class ProfileStore:
    """Offline-first JSON store for ``BioProfile`` documents."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._base = Path(hass.config.path(LOCAL_RELATIVE_PATH)) / PROFILES_DIRNAME
        self._lock = asyncio.Lock()

    async def async_init(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    async def async_list(self) -> list[str]:
        names: list[str] = []
        for path in self._base.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                names.append(path.stem)
                continue

            if not isinstance(raw, Mapping):
                names.append(path.stem)
                continue

            payload = self._normalise_payload(raw, fallback_name=path.stem)
            name = payload.get("display_name") or payload.get("name") or path.stem
            names.append(str(name))

        return sorted(names, key=str.casefold)

    async def async_list_profiles(self) -> list[str]:
        return await self.async_list()

    async def async_get(self, name: str) -> dict[str, Any] | None:
        path = self._path_for(name)
        if not path.exists():
            return None
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(raw, Mapping):
            return None

        return self._normalise_payload(raw, fallback_name=path.stem)

    async def async_save(
        self,
        profile: BioProfile | dict[str, Any],
        *,
        name: str | None = None,
    ) -> None:
        if isinstance(profile, BioProfile):
            profile_obj = deepcopy(profile)
            payload = self._profile_to_payload(profile_obj)
            target_name = name or profile_obj.display_name or profile_obj.profile_id
        else:
            fallback = (
                name or profile.get("display_name") or profile.get("name") or profile.get("plant_id") or "profile"
            )
            if fallback == "profile":
                identifier = profile.get("profile_id")
                if isinstance(identifier, str) and identifier.strip():
                    fallback = identifier
            preserved: dict[str, Any] = {}
            for key in ("species_display", "species_pid", "image_url"):
                value = profile.get(key)
                if isinstance(value, str) and value:
                    preserved[key] = value
            credentials = profile.get("opb_credentials")
            if isinstance(credentials, Mapping):
                preserved["opb_credentials"] = deepcopy(dict(credentials))
            payload = self._normalise_payload(profile, fallback_name=fallback)
            if preserved:
                payload.update(preserved)
            target_name = fallback
        await self._atomic_write(self._path_for(target_name), payload)

    async def async_create_profile(
        self,
        name: str,
        sensors: dict[str, str] | None = None,
        clone_from: dict[str, Any] | None = None,
        scope: str | None = None,
    ) -> None:
        clone_profile: BioProfile | None = None
        clone_payload: Mapping[str, Any] | None = None
        if isinstance(clone_from, str) and clone_from:
            payload = await self.async_get(clone_from)
            if payload:
                clone_payload = payload
                clone_profile = self._as_profile(payload, fallback_name=clone_from)
        elif isinstance(clone_from, dict):
            clone_payload = _mutable_copy(clone_from)
            clone_profile = self._as_profile(clone_payload, fallback_name=name)

        sensors_data: dict[str, str]
        if sensors is not None:
            sensors_data = {
                str(key): value.strip() for key, value in sensors.items() if isinstance(value, str) and value.strip()
            }
        elif clone_profile and isinstance(clone_profile.general.get("sensors"), dict):
            sensors_data = {
                str(key): value.strip()
                for key, value in clone_profile.general.get("sensors", {}).items()
                if isinstance(value, str) and value.strip()
            }
        else:
            sensors_data = {}

        resolved_scope = scope
        if resolved_scope is None and clone_profile is not None:
            resolved_scope = clone_profile.general.get(CONF_PROFILE_SCOPE)

        slug = slugify(name) or "profile"

        if clone_profile is not None:
            new_profile = BioProfile(
                profile_id=slug,
                display_name=name,
                profile_type=clone_profile.profile_type,
                species=clone_profile.species,
                tenant_id=clone_profile.tenant_id,
                parents=list(clone_profile.parents),
                identity=dict(clone_profile.identity),
                taxonomy=dict(clone_profile.taxonomy),
                policies=dict(clone_profile.policies),
                stable_knowledge=dict(clone_profile.stable_knowledge),
                lifecycle=dict(clone_profile.lifecycle),
                traits=dict(clone_profile.traits),
                tags=list(clone_profile.tags),
                curated_targets=dict(clone_profile.curated_targets),
                diffs_vs_parent=dict(clone_profile.diffs_vs_parent),
                library_metadata=dict(clone_profile.library_metadata),
                library_created_at=clone_profile.library_created_at,
                library_updated_at=clone_profile.library_updated_at,
                local_overrides=dict(clone_profile.local_overrides),
                resolver_state=dict(clone_profile.resolver_state),
                resolved_targets={k: deepcopy(v) for k, v in clone_profile.resolved_targets.items()},
                computed_stats=[deepcopy(stat) for stat in clone_profile.computed_stats],
                general=deepcopy(clone_profile.general),
                citations=[deepcopy(cit) for cit in clone_profile.citations],
                local_metadata=dict(clone_profile.local_metadata),
                run_history=[deepcopy(event) for event in clone_profile.run_history],
                harvest_history=[deepcopy(event) for event in clone_profile.harvest_history],
                statistics=[deepcopy(stat) for stat in clone_profile.statistics],
                last_resolved=clone_profile.last_resolved,
                created_at=clone_profile.created_at,
                updated_at=clone_profile.updated_at,
            )
        else:
            new_profile = BioProfile(
                profile_id=slug,
                display_name=name,
            )

        if sensors_data:
            new_profile.general["sensors"] = dict(sensors_data)
        if resolved_scope is not None:
            new_profile.general[CONF_PROFILE_SCOPE] = resolved_scope

        new_profile.refresh_sections()
        preserved: dict[str, Any] = {}
        if isinstance(clone_payload, Mapping):
            for key in ("species_display", "species_pid", "image_url"):
                value = clone_payload.get(key)
                if isinstance(value, str) and value:
                    preserved[key] = value
            credentials = clone_payload.get("opb_credentials")
            if isinstance(credentials, Mapping):
                preserved["opb_credentials"] = deepcopy(dict(credentials))

        payload = self._profile_to_payload(new_profile)
        if preserved:
            payload.update(preserved)

        await self.async_save(payload, name=name)

    async def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        txt = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        async with self._lock:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(path)

    def _path_for(self, name: Any) -> Path:
        base = _slug_source(name)
        slug = slugify(base) or (base if base else "profile")
        return self._base / f"{slug}.json"

    def _normalise_payload(self, payload: dict[str, Any], *, fallback_name: Any) -> dict[str, Any]:
        base = _slug_source(fallback_name)
        slug = slugify(base) or (base if base else "profile")
        preserved: dict[str, Any] = {}
        for key in ("species_display", "species_pid", "image_url"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                preserved[key] = value
        credentials = payload.get("opb_credentials")
        if isinstance(credentials, Mapping):
            preserved["opb_credentials"] = deepcopy(dict(credentials))
        normalised = normalise_profile_payload(payload, fallback_id=str(slug), display_name=fallback_name)
        profile = BioProfile.from_json(normalised)
        output = self._profile_to_payload(profile)
        if preserved:
            output.update(preserved)
        return output

    def _as_profile(self, payload: dict[str, Any], *, fallback_name: Any) -> BioProfile:
        data = deepcopy(payload)
        display_name = data.get("display_name") or data.get("name") or fallback_name
        display_base = _slug_source(display_name)
        fallback_base = _slug_source(fallback_name)
        slug = (
            data.get("profile_id")
            or data.get("plant_id")
            or slugify(display_base)
            or slugify(fallback_base)
            or "profile"
        )
        normalised = normalise_profile_payload(data, fallback_id=str(slug), display_name=display_name)
        normalised.setdefault("name", normalised.get("display_name"))
        return BioProfile.from_json(normalised)

    def _profile_to_payload(self, profile: BioProfile) -> dict[str, Any]:
        data = profile.to_json()
        data["name"] = profile.display_name
        general = data.get("general") if isinstance(data.get("general"), dict) else {}
        if general:
            data["general"] = general
        sensors = general.get("sensors") if isinstance(general.get("sensors"), dict) else None
        if sensors:
            data["sensors"] = dict(sensors)
        scope = general.get(CONF_PROFILE_SCOPE)
        if scope is not None:
            data["scope"] = scope
        template = general.get("template")
        if template is not None:
            data["template"] = template
        return data
