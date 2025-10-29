from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .cloudsync import EdgeResolverService
from .const import CONF_PROFILES, DOMAIN, OPB_FIELD_MAP, VARIABLE_SPECS
from .profile.options import options_profile_to_dataclass
from .profile.resolution import (
    annotate_inherited_target,
    build_profiles_index,
    resolve_inheritance_target,
)
from .profile.schema import BioProfile, FieldAnnotation, ResolvedTarget
from .profile.utils import (
    citations_map_to_list,
    determine_species_slug,
    ensure_sections,
)

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

_LOGGER = logging.getLogger(__name__)


def _coerce_ttl_hours(value: Any, *, default: float) -> float:
    """Return a positive ``ttl_hours`` value or ``default`` when invalid."""

    candidate: float
    if isinstance(value, int | float):
        candidate = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return float(default)
        try:
            candidate = float(text)
        except (TypeError, ValueError):
            return float(default)
    else:
        return float(default)

    if not math.isfinite(candidate) or candidate <= 0:
        return float(default)
    return candidate


class PreferenceResolver:
    """Resolves per-variable values from manual/clone/opb/ai with TTL + citations."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._missing_inheritance: set[tuple[str, str]] = set()

    def _cloud_store(self, entry) -> tuple[Any | None, str | None, str | None]:
        """Return the cloud sync store, tenant, and organization context if available."""

        domain_data = self.hass.data.get(DOMAIN)
        if not isinstance(domain_data, Mapping):
            return None, None, None
        entry_id = getattr(entry, "entry_id", None)
        if entry_id is None:
            return None, None, None
        entry_data = domain_data.get(entry_id)
        if not isinstance(entry_data, Mapping):
            return None, None, None
        manager = entry_data.get("cloud_sync_manager")
        if manager is None:
            return None, None, None
        store = getattr(manager, "store", None)
        tenant_id = None
        organization_id = None
        config = getattr(manager, "config", None)
        if config is not None:
            tenant_value = getattr(config, "tenant_id", None)
            if isinstance(tenant_value, str) and tenant_value.strip():
                tenant_id = tenant_value.strip()
            org_value = getattr(config, "organization_id", None)
            if isinstance(org_value, str) and org_value.strip():
                organization_id = org_value.strip()
        return store, tenant_id, organization_id

    def _profile_registry(self, entry) -> Any | None:
        """Return the profile registry stored for ``entry``."""

        domain_data = self.hass.data.get(DOMAIN)
        if not isinstance(domain_data, Mapping):
            return None
        entry_id = getattr(entry, "entry_id", None)
        if entry_id is None:
            return None
        entry_data = domain_data.get(entry_id)
        if not isinstance(entry_data, Mapping):
            return None
        registry = entry_data.get("profile_registry") or entry_data.get("profiles")
        if registry is None:
            registry = entry_data.get("registry")
        return registry

    def _load_local_payload(self, entry, profile_id: str) -> dict[str, Any]:
        """Return a local payload mapping for ``profile_id``."""

        profiles = entry.options.get(CONF_PROFILES, {}) if isinstance(entry.options, Mapping) else {}
        payload = profiles.get(profile_id)
        if not isinstance(payload, Mapping):
            return {}
        data = dict(payload)
        ensure_sections(data, plant_id=profile_id, display_name=data.get("name") or profile_id)
        local_section = data.get("local")
        if isinstance(local_section, Mapping):
            return {str(key): value for key, value in local_section.items()}
        return {}

    def _overlay_cloud_profile(
        self,
        entry,
        profile_id: str,
        profile: BioProfile,
        profile_payload: Mapping[str, Any],
    ) -> BioProfile | None:
        """Combine cloud snapshots with local profile state if available."""

        store, tenant_id, organization_id = self._cloud_store(entry)
        if store is None:
            return None

        local_payload = profile_payload.get("local") if isinstance(profile_payload, Mapping) else {}
        local_map = dict(local_payload) if isinstance(local_payload, Mapping) else {}

        def local_loader(pid: str) -> dict[str, Any]:
            if pid == profile_id:
                return dict(local_map)
            return self._load_local_payload(entry, pid)

        resolver = EdgeResolverService(
            store,
            local_profile_loader=local_loader,
            tenant_id=tenant_id,
            organization_id=organization_id,
        )
        try:
            resolved = resolver.resolve_profile(profile_id, local_payload=local_map)
        except Exception:  # pragma: no cover - defensive fallback
            return None

        for key, target in profile.resolved_targets.items():
            resolved.resolved_targets.setdefault(key, target)
        if profile.resolver_state:
            resolved.resolver_state = dict(profile.resolver_state)
        if profile.local_overrides:
            merged_overrides = dict(resolved.local_overrides)
            for key, value in profile.local_overrides.items():
                merged_overrides.setdefault(key, value)
            resolved.local_overrides = merged_overrides
        resolved.local_metadata = dict(profile.local_metadata)
        resolved.general = dict(profile.general)
        resolved.citations = list(profile.citations)
        resolved.last_resolved = profile.last_resolved
        resolved.created_at = profile.created_at
        resolved.updated_at = profile.updated_at
        if profile.lineage and not resolved.lineage:
            resolved.lineage = list(profile.lineage)
        resolved.sections = None
        resolved._ensure_sections()
        return resolved

    async def resolve_profile(self, entry, profile_id: str) -> dict[str, Any]:
        prof = dict(entry.options.get(CONF_PROFILES, {}).get(profile_id, {}))
        profile = options_profile_to_dataclass(
            profile_id,
            prof,
            display_name=prof.get("name") or profile_id,
        )
        registry_profile = None
        registry = self._profile_registry(entry)
        if registry is not None:
            getter = getattr(registry, "get_profile", None)
            if getter is not None:
                registry_profile = getter(profile_id)
        if registry_profile and getattr(registry_profile, "lineage", None):
            profile.lineage = list(registry_profile.lineage)
        sources = dict(prof.get("sources", {}))
        thresholds = dict(prof.get("thresholds", {}))
        citations = dict(prof.get("citations", {}))
        resolved_targets: dict[str, ResolvedTarget] = dict(profile.resolved_targets)
        changed = False
        changed_fields: list[str] = []

        for key, *_ in VARIABLE_SPECS:
            target = await self._resolve_variable(
                entry,
                profile_id,
                key,
                sources.get(key),
                thresholds,
                entry.options,
            )
            if target is None:
                continue

            thresholds[key] = target.value

            detail: str | None = None
            extras = target.annotation.extras or {}
            if isinstance(extras, dict):
                detail = extras.get("source_detail") or extras.get("summary") or extras.get("notes")
            if not detail and target.annotation.method:
                detail = target.annotation.method
            if not detail and target.annotation.source_ref:
                detail = ",".join(target.annotation.source_ref)
            if not detail and target.citations:
                first = target.citations[0]
                if isinstance(first.details, dict):
                    detail = first.details.get("note") or first.details.get("summary")
                detail = detail or first.title

            citations[key] = {
                "mode": target.annotation.source_type,
                "ts": datetime.now(UTC).isoformat(),
                "source_detail": detail,
            }

            resolved_targets[str(key)] = target
            changed_fields.append(str(key))
            changed = True

        if changed:
            resolved_at = datetime.now(UTC).isoformat()
            profile.resolved_targets = resolved_targets
            profile.citations = citations_map_to_list(citations)
            source_snapshot: dict[str, Any] = {}
            if isinstance(sources, Mapping):
                for key, value in sources.items():
                    if isinstance(value, Mapping):
                        source_snapshot[key] = dict(value)
                    else:
                        source_snapshot[key] = value

            profile.resolver_state = {
                "sources": source_snapshot,
                "resolved_keys": sorted(thresholds.keys()),
                "updated_at": resolved_at,
            }
            local_metadata = dict(profile.local_metadata)
            local_metadata["citation_map"] = citations
            local_metadata["resolved_fields"] = sorted(set(changed_fields))
            local_metadata["resolved_at"] = resolved_at
            profile.local_metadata = local_metadata
            profile.last_resolved = resolved_at
            profile.updated_at = resolved_at

            general = dict(profile.general)
            if isinstance(prof.get("general"), Mapping):
                general.update(dict(prof["general"]))
            profile.general = general

            profile.sections = None
            profile_payload = profile.to_json()
            cloud_profile = self._overlay_cloud_profile(entry, profile_id, profile, profile_payload)
            if cloud_profile is not None:
                profile = cloud_profile
                profile_payload = profile.to_json()

            prof.update(
                {
                    "thresholds": profile_payload.get("thresholds", {}),
                    "resolved_targets": profile_payload.get("resolved_targets", {}),
                    "variables": profile_payload.get("variables", {}),
                    "general": profile_payload.get("general", {}),
                    "citations": citations,
                    "profile_citations": profile_payload.get("citations", []),
                    "local": profile_payload.get("local", {}),
                    "library": profile_payload.get("library", {}),
                    "sections": profile_payload.get("sections", {}),
                    "lineage": profile_payload.get("lineage", []),
                    "needs_resolution": False,
                    "last_resolved": resolved_at,
                    "resolver_state": profile.resolver_state,
                    "local_overrides": profile.local_overrides,
                    "local_metadata": profile.local_metadata,
                    "library_metadata": profile.library_metadata,
                    "library_created_at": profile.library_created_at,
                    "library_updated_at": profile.library_updated_at,
                    "profile_type": profile.profile_type,
                    "species": profile.species,
                    "tenant_id": profile.tenant_id,
                    "parents": list(profile.parents),
                    "tags": list(profile.tags),
                    "identity": dict(profile.identity),
                    "taxonomy": dict(profile.taxonomy),
                    "policies": dict(profile.policies),
                    "stable_knowledge": dict(profile.stable_knowledge),
                    "lifecycle": dict(profile.lifecycle),
                    "traits": dict(profile.traits),
                    "curated_targets": dict(profile.curated_targets),
                    "diffs_vs_parent": dict(profile.diffs_vs_parent),
                    "run_history": [event.to_json() for event in profile.run_history],
                    "harvest_history": [event.to_json() for event in profile.harvest_history],
                    "statistics": [stat.to_json() for stat in profile.statistics],
                }
            )
            prof["computed_stats"] = profile_payload.get("computed_stats", [])

            allp = dict(entry.options.get(CONF_PROFILES, {}))
            allp[profile_id] = prof
            opts = dict(entry.options)
            opts[CONF_PROFILES] = allp
            self.hass.config_entries.async_update_entry(entry, options=opts)
            with suppress(AttributeError):  # pragma: no cover - defensive when entry immutable
                entry.options = opts

        return thresholds

    async def _resolve_variable(
        self,
        entry,
        profile_id: str,
        key: str,
        src: dict | None,
        thresholds: dict,
        options: dict,
    ) -> ResolvedTarget | None:
        if not src:
            return self._resolve_via_inheritance(entry, profile_id, key)

        mode = src.get("mode") if isinstance(src, Mapping) else None

        if mode in (None, "inheritance", "inherit"):
            fallback = self._resolve_via_inheritance(entry, profile_id, key)
            if fallback is not None:
                return fallback
            if mode in ("inheritance", "inherit"):
                return None

        try:
            if mode == "manual":
                return await resolve_variable_from_source(
                    self.hass,
                    plant_id=profile_id,
                    key=key,
                    source="manual",
                    manual_value=src.get("value"),
                )

            if mode == "clone":
                clone_from = src.get("copy_from")
                profiles_map = options.get(CONF_PROFILES) or {}
                if clone_from and clone_from in profiles_map:
                    other = profiles_map[clone_from]
                    resolved_payload = (other.get("resolved_targets") or {}).get(key)
                    if isinstance(resolved_payload, dict):
                        return ResolvedTarget.from_json(resolved_payload)
                    fallback = (other.get("thresholds") or {}).get(key)
                    if fallback is not None:
                        from .profile.citations import clone_ref

                        annotation = FieldAnnotation(
                            source_type="clone",
                            method="clone",
                            source_ref=[clone_from],
                            extras={"clone_profile_id": clone_from},
                        )
                        citations = [clone_ref(clone_from, key)]
                        return ResolvedTarget(value=fallback, annotation=annotation, citations=citations)

                return await resolve_variable_from_source(
                    self.hass,
                    plant_id=profile_id,
                    key=key,
                    source="clone",
                    clone_from=clone_from,
                )

            if mode == "opb":
                return await resolve_variable_from_source(
                    self.hass,
                    plant_id=profile_id,
                    key=key,
                    source="openplantbook",
                    opb_args=src.get("opb"),
                )

            if mode == "ai":
                raw_ai = src.get("ai", {}) or {}
                ai = dict(raw_ai) if isinstance(raw_ai, Mapping) else {}
                ttl_h = _coerce_ttl_hours(ai.get("ttl_hours"), default=720)
                ai["ttl_hours"] = ttl_h
                last_run = ai.get("last_run")
                if last_run:
                    ts = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    if datetime.now(UTC) - ts < timedelta(hours=ttl_h):
                        prof = options.get(CONF_PROFILES, {}).get(profile_id, {})
                        payload = (prof.get("resolved_targets") or {}).get(key)
                        if isinstance(payload, dict):
                            cached = ResolvedTarget.from_json(payload)
                            if cached.annotation.confidence is None:
                                cached.annotation.confidence = ai.get("confidence")
                            return cached
                        annotation = FieldAnnotation(
                            source_type="ai",
                            method=ai.get("model") or ai.get("provider") or "ai",
                            confidence=ai.get("confidence"),
                            extras={
                                key: value
                                for key, value in {
                                    "notes": ai.get("notes"),
                                    "links": ai.get("links"),
                                    "summary": ai.get("summary"),
                                }.items()
                                if value
                            },
                        )
                        return ResolvedTarget(value=thresholds.get(key), annotation=annotation)

                result = await resolve_variable_from_source(
                    self.hass,
                    plant_id=profile_id,
                    key=key,
                    source="ai",
                    ai_args=ai,
                )
                if result is not None:
                    self._update_ai_cache(
                        entry,
                        profile_id,
                        key,
                        result.value,
                        result.annotation.confidence,
                        (result.annotation.extras or {}).get("summary"),
                        (result.annotation.extras or {}).get("links"),
                    )
                return result

        except ValueError:
            return None

        return None

    def _resolve_via_inheritance(self, entry, profile_id: str, key: str) -> ResolvedTarget | None:
        registry = self._profile_registry(entry)
        if registry is None:
            return None

        getter = getattr(registry, "get_profile", None)
        if getter is None:
            return None

        profile = getter(profile_id)
        if profile is None:
            return None

        if hasattr(registry, "iter_profiles"):
            all_profiles = list(registry.iter_profiles())  # type: ignore[call-arg]
        elif hasattr(registry, "list_profiles"):
            all_profiles = list(registry.list_profiles())  # type: ignore[call-arg]
        else:
            all_profiles = [profile]

        profiles_by_id = build_profiles_index(all_profiles)
        profiles_by_id.setdefault(profile.profile_id, profile)

        resolution = resolve_inheritance_target(profile, key, profiles_by_id)
        if resolution is None:
            if profile.profile_type != "species":
                cache_key = (profile.profile_id, key)
                if cache_key not in self._missing_inheritance:
                    self._missing_inheritance.add(cache_key)
                    _LOGGER.warning(
                        "Inheritance lookup for '%s' on profile %s (%s) failed; check cultivar/species defaults.",
                        key,
                        profile.display_name,
                        profile.profile_id,
                    )
            return None

        return annotate_inherited_target(resolution)

    def _update_ai_cache(self, entry, pid, key, val, conf, notes, links):
        opts = dict(entry.options)
        prof = dict(opts.get(CONF_PROFILES, {}).get(pid, {}))
        sources = dict(prof.get("sources", {}))
        ai = dict(sources.get(key, {}).get("ai", {}))
        ai["last_run"] = datetime.now(UTC).isoformat()
        ai["confidence"] = conf
        ai["notes"] = notes
        ai["links"] = links
        s = dict(sources.get(key, {}))
        s["ai"] = ai
        sources[key] = s
        prof["sources"] = sources
        allp = dict(opts.get(CONF_PROFILES, {}))
        allp[pid] = prof
        opts[CONF_PROFILES] = allp
        self.hass.config_entries.async_update_entry(entry, options=opts)
        with suppress(AttributeError):  # pragma: no cover - defensive when entry immutable
            entry.options = opts


async def generate_profile(
    hass: HomeAssistant,
    entry,
    profile_id: str,
    mode: str,
    source_profile_id: str | None = None,
) -> None:
    """Populate all variables for a profile from a single source and resolve immediately."""

    opts = dict(entry.options)
    prof = dict(opts.get(CONF_PROFILES, {}).get(profile_id, {}))
    library_section, local_section = ensure_sections(
        prof,
        plant_id=profile_id,
        display_name=prof.get("name") or profile_id,
    )
    sources = dict(prof.get("sources", {}))
    slug = determine_species_slug(
        library=library_section,
        local=local_section,
        raw=prof.get("species"),
    )

    if mode == "clone":
        if not source_profile_id:
            raise ValueError("source_profile_id required for clone")
        other = dict(opts.get(CONF_PROFILES, {}).get(source_profile_id, {}))
        ensure_sections(
            other,
            plant_id=source_profile_id,
            display_name=other.get("name") or source_profile_id,
        )
        thresholds = dict(other.get("thresholds", {}))
        prof["thresholds"] = thresholds
        for key, *_ in VARIABLE_SPECS:
            sources[key] = {"mode": "clone", "copy_from": source_profile_id}
    else:
        for key, *_ in VARIABLE_SPECS:
            if mode == "opb":
                field = OPB_FIELD_MAP.get(key, key)
                sources[key] = {
                    "mode": "opb",
                    "opb": {"species": slug, "field": field},
                }
            else:
                sources[key] = {
                    "mode": "ai",
                    "ai": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "ttl_hours": 720,
                    },
                }

    prof["sources"] = sources
    prof["needs_resolution"] = True
    allp = dict(opts.get(CONF_PROFILES, {}))
    allp[profile_id] = prof
    opts[CONF_PROFILES] = allp
    hass.config_entries.async_update_entry(entry, options=opts)
    with suppress(AttributeError):  # pragma: no cover - defensive when entry immutable
        entry.options = opts

    resolver = PreferenceResolver(hass)
    await resolver.resolve_profile(entry, profile_id)

    from .profile.store import async_save_profile_from_options

    await async_save_profile_from_options(hass, entry, profile_id)


async def resolve_variable_from_source(
    hass: HomeAssistant,
    *,
    plant_id: str,
    key: str,
    source: str,
    manual_value: Any | None = None,
    clone_from: str | None = None,
    opb_args: dict[str, Any] | None = None,
    ai_args: dict[str, Any] | None = None,
) -> ResolvedTarget:
    """Resolve a single target value based on the selected source."""

    from .ai_client import async_recommend_variable
    from .opb_client import async_fetch_field
    from .profile.citations import ai_ref, clone_ref, manual_note, opb_ref
    from .profile.store import async_get_profile

    citations = []
    if source == "manual":
        citations.append(manual_note("Set via options UI"))
        annotation = FieldAnnotation(source_type=source, method=source)
        return ResolvedTarget(value=manual_value, annotation=annotation, citations=citations)

    if source == "clone":
        if not clone_from:
            raise ValueError("clone_from required")
        src = await async_get_profile(hass, clone_from)
        value: Any | None = None
        if src:
            resolved_section = src.get("resolved_targets")
            if isinstance(resolved_section, dict) and key in resolved_section:
                payload = resolved_section[key]
                if isinstance(payload, dict):
                    value = payload.get("value")
            elif key in (src.get("variables") or {}):
                value = src["variables"][key].get("value")
        if value is None:
            raise ValueError("Clone source missing variable")
        citations.append(clone_ref(clone_from, key))
        annotation = FieldAnnotation(
            source_type=source,
            method=source,
            source_ref=[clone_from],
            extras={"clone_profile_id": clone_from},
        )
        return ResolvedTarget(value=value, annotation=annotation, citations=citations)

    if source == "openplantbook":
        field = (opb_args or {}).get("field")
        species = (opb_args or {}).get("species")
        value, url = await async_fetch_field(hass, species=species, field=field)
        citations.append(opb_ref(species, field, url))
        extras = {key: val for key, val in (("field", field), ("url", url)) if val}
        annotation = FieldAnnotation(
            source_type=source,
            method=source,
            source_ref=[species] if species else [],
            extras=extras,
        )
        return ResolvedTarget(value=value, annotation=annotation, citations=citations)

    if source == "ai":
        result = await async_recommend_variable(hass, key=key, plant_id=plant_id, **(ai_args or {}))
        value = result.get("value")
        summary = result.get("summary", "AI generated recommendation")
        links = result.get("links", [])
        citations.append(ai_ref(summary, links))
        annotation = FieldAnnotation(
            source_type=source,
            method=result.get("model") or result.get("provider") or source,
            confidence=result.get("confidence"),
            extras={"summary": summary, "links": links},
        )
        return ResolvedTarget(value=value, annotation=annotation, citations=citations)

    raise ValueError(f"Unknown source: {source}")
