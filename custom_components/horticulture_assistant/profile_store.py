from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence, Set
from copy import deepcopy
from enum import Enum
from math import isfinite
from numbers import Integral, Real
from pathlib import Path, PurePath
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import CONF_PROFILE_SCOPE, PROFILE_SCOPE_CHOICES, PROFILE_SCOPE_DEFAULT
from .profile.schema import BioProfile, CultivarProfile, SpeciesProfile
from .profile.utils import normalise_profile_payload

LOCAL_RELATIVE_PATH = "custom_components/horticulture_assistant/data/local"
PROFILES_DIRNAME = "profiles"


_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *{f"com{idx}" for idx in range(1, 10)},
    *{f"lpt{idx}" for idx in range(1, 10)},
}

_WINDOWS_INVALID_CHARS = "<>:\\\"|?*"


def _normalise_metadata_value(value: Any) -> str | None:
    """Return a string representation for preserved metadata keys."""

    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        number = float(value)
        if not isfinite(number):
            return None
        return format(number, "g")
    return None


def _slug_source(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _normalise_scope(value: Any) -> str | None:
    """Return a canonical profile scope string if ``value`` is valid."""

    if isinstance(value, Enum):
        candidate = value.value
        value = candidate if isinstance(candidate, str) else str(candidate)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    lowered = text.casefold()
    for choice in PROFILE_SCOPE_CHOICES:
        if lowered == choice.casefold():
            return choice
    return None


def _clone_structure(value: Any) -> Any:
    """Recursively clone ``value`` while normalising mapping proxies."""

    if isinstance(value, dict):
        return {key: _clone_structure(item) for key, item in value.items()}
    if isinstance(value, Mapping):
        return {key: _clone_structure(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_structure(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_structure(item) for item in value)
    return deepcopy(value)


def _normalise_sensor_binding(value: Any) -> str | list[str] | None:
    """Normalise sensor mapping values to trimmed strings or lists."""

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    if isinstance(value, Set):
        cleaned: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            trimmed = item.strip()
            if trimmed:
                cleaned.append(trimmed)
        if cleaned:
            deduped = sorted(dict.fromkeys(cleaned), key=str.casefold)
            return deduped
        return None

    if isinstance(value, (bytes, bytearray)):  # noqa: UP038 - Union type raises at runtime
        return None

    if isinstance(value, Sequence):
        items: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            trimmed = item.strip()
            if trimmed and trimmed not in seen:
                items.append(trimmed)
                seen.add(trimmed)
        if items:
            deduped = list(dict.fromkeys(items))
            return deduped
        return None

    return None


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
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                names.append(path.stem)
                continue

            if not isinstance(raw, Mapping):
                names.append(path.stem)
                continue

            try:
                payload = self._normalise_payload(raw, fallback_name=path.stem)
            except asyncio.CancelledError:  # pragma: no cover - propagate cancellation
                raise
            except Exception:  # pragma: no cover - invalid payload
                names.append(path.stem)
                continue
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
        except (OSError, UnicodeDecodeError):
            return None
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        if not isinstance(raw, Mapping):
            return None

        try:
            return self._normalise_payload(raw, fallback_name=path.stem)
        except asyncio.CancelledError:  # pragma: no cover - propagate cancellation
            raise
        except Exception:  # pragma: no cover - invalid payload
            return None

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
                normalised = _normalise_metadata_value(profile.get(key))
                if normalised is not None:
                    preserved[key] = normalised
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
            clone_payload = clone_from
            clone_profile = self._as_profile(clone_from, fallback_name=name)

        sensors_data: dict[str, str | list[str]]
        explicit_sensors = sensors is not None
        if explicit_sensors:
            sensors_data = {}
            for key, value in sensors.items():
                key_text = str(key)
                if not key_text:
                    continue
                normalised = _normalise_sensor_binding(value)
                if normalised is not None:
                    sensors_data[key_text] = normalised
        elif clone_profile and isinstance(clone_profile.general.get("sensors"), dict):
            sensors_data = {}
            for key, value in clone_profile.general.get("sensors", {}).items():
                if not isinstance(key, str):
                    continue
                normalised = _normalise_sensor_binding(value)
                if normalised is not None:
                    sensors_data[str(key)] = normalised
        else:
            sensors_data = {}

        resolved_scope = _normalise_scope(scope)
        if resolved_scope is None and clone_profile is not None:
            resolved_scope = _normalise_scope(clone_profile.general.get(CONF_PROFILE_SCOPE))
        if resolved_scope is None and isinstance(clone_payload, Mapping):
            resolved_scope = _normalise_scope(clone_payload.get(CONF_PROFILE_SCOPE) or clone_payload.get("scope"))
        if resolved_scope is None:
            resolved_scope = PROFILE_SCOPE_DEFAULT

        slug = self._unique_slug(name)

        if clone_profile is not None:
            profile_cls: type[BioProfile] = type(clone_profile)
            extra_kwargs: dict[str, Any] = {}
            if not issubclass(profile_cls, BioProfile):
                profile_cls = BioProfile
            else:
                if isinstance(clone_profile, SpeciesProfile):
                    extra_kwargs["cultivar_ids"] = list(clone_profile.cultivar_ids)
                if isinstance(clone_profile, CultivarProfile):
                    extra_kwargs["area_m2"] = clone_profile.area_m2

            new_profile = profile_cls(
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
                **extra_kwargs,
            )
        else:
            new_profile = BioProfile(
                profile_id=slug,
                display_name=name,
            )

        if explicit_sensors:
            if sensors_data:
                new_profile.general["sensors"] = dict(sensors_data)
            else:
                new_profile.general.pop("sensors", None)
        elif sensors_data:
            new_profile.general["sensors"] = dict(sensors_data)
        if resolved_scope is not None:
            new_profile.general[CONF_PROFILE_SCOPE] = resolved_scope

        new_profile.refresh_sections()
        preserved: dict[str, Any] = {}
        if isinstance(clone_payload, Mapping):
            for key in ("species_display", "species_pid", "image_url"):
                normalised = _normalise_metadata_value(clone_payload.get(key))
                if normalised is not None:
                    preserved[key] = normalised
            credentials = clone_payload.get("opb_credentials")
            if isinstance(credentials, Mapping):
                preserved["opb_credentials"] = deepcopy(dict(credentials))

        payload = self._profile_to_payload(new_profile)
        if preserved:
            payload.update(preserved)

        await self.async_save(payload, name=slug)

    async def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        txt = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        async with self._lock:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(path)

    def _path_for(self, name: Any) -> Path:
        base = _slug_source(name)
        slug = self._safe_slug(base)
        return self._base / f"{slug}.json"

    def _unique_slug(self, name: Any) -> str:
        """Return a filesystem-safe slug that does not collide with existing files."""

        base = _slug_source(name)
        slug = self._safe_slug(base)
        candidate = slug
        suffix = 2
        while (self._base / f"{candidate}.json").exists():
            candidate = f"{slug}_{suffix}"
            suffix += 1
        return candidate

    def _safe_slug(self, base: str) -> str:
        """Return a filesystem-safe slug limited to a single path component."""

        for candidate in (slugify(base), base):
            safe = self._normalise_slug_component(candidate)
            if safe:
                return safe
        return "profile"

    @staticmethod
    def _normalise_slug_component(candidate: str | None) -> str | None:
        if not candidate:
            return None
        text = str(candidate).strip()
        if not text:
            return None
        # Normalise both POSIX and Windows separators so ``PurePath`` can enforce a
        # single path component.
        text = text.replace("\\", "/")
        pure = PurePath(text)
        normalised_parts: list[str] = []
        for segment in pure.parts:
            cleaned = segment.strip()
            if not cleaned or cleaned in {".", ".."}:
                continue
            normalised_parts.append(cleaned)
        part = "_".join(normalised_parts) if normalised_parts else pure.name if len(pure.parts) != 1 else pure.parts[0]
        part = part.strip().strip(".")
        if not part:
            return None
        if part in {".", ".."}:
            return None
        if "/" in part or "\\" in part:
            part = part.replace("/", "_").replace("\\", "_")
        if any(char in part for char in _WINDOWS_INVALID_CHARS):
            for char in _WINDOWS_INVALID_CHARS:
                if char in part:
                    part = part.replace(char, "_")
        part = part.strip().strip(".")
        if not part or part in {".", ".."}:
            return None
        primary, *suffix_parts = part.split(".")
        stem = primary.lower()
        if stem in _WINDOWS_RESERVED_NAMES:
            safe = f"{stem}_profile"
            if suffix_parts:
                cleaned_suffix = "_".join(segment for segment in suffix_parts if segment)
                cleaned_suffix = cleaned_suffix.replace(".", "_").strip("_")
                if cleaned_suffix:
                    safe = f"{safe}_{cleaned_suffix}"
            part = safe
        else:
            suffix_parts = [segment for segment in suffix_parts if segment]
            if suffix_parts:
                suffix = "_".join(item.replace(".", "_") for item in suffix_parts)
                part = f"{primary}_{suffix}" if primary else suffix
            else:
                part = primary

        part = part.replace(".", "_")
        part = part.strip("_")
        if not part:
            return None
        return part

    def _normalise_payload(self, payload: dict[str, Any], *, fallback_name: Any) -> dict[str, Any]:
        base = _slug_source(fallback_name)
        slug = slugify(base) or (base if base else "profile")
        preserved: dict[str, Any] = {}
        for key in ("species_display", "species_pid", "image_url"):
            normalised = _normalise_metadata_value(payload.get(key))
            if normalised is not None:
                preserved[key] = normalised
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
        data = _clone_structure(payload)
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
