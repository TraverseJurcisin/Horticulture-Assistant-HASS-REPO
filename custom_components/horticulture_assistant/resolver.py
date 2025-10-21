from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

from .const import OPB_FIELD_MAP, VARIABLE_SPECS
from .profile.options import options_profile_to_dataclass
from .profile.schema import FieldAnnotation, ResolvedTarget
from .profile.utils import (
    citations_map_to_list,
    determine_species_slug,
    ensure_sections,
)

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

class PreferenceResolver:
    """Resolves per-variable values from manual/clone/opb/ai with TTL + citations."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def resolve_profile(self, entry, profile_id: str) -> dict[str, Any]:
        prof = dict(entry.options.get("profiles", {}).get(profile_id, {}))
        profile = options_profile_to_dataclass(
            profile_id,
            prof,
            display_name=prof.get("name") or profile_id,
        )
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
                detail = (
                    extras.get("source_detail")
                    or extras.get("summary")
                    or extras.get("notes")
                )
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
                    "needs_resolution": False,
                    "last_resolved": resolved_at,
                    "resolver_state": profile.resolver_state,
                    "local_overrides": profile.local_overrides,
                    "local_metadata": profile.local_metadata,
                    "library_metadata": profile.library_metadata,
                    "library_created_at": profile.library_created_at,
                    "library_updated_at": profile.library_updated_at,
                }
            )
            if profile_payload.get("computed_stats"):
                prof["computed_stats"] = profile_payload["computed_stats"]

            allp = dict(entry.options.get("profiles", {}))
            allp[profile_id] = prof
            opts = dict(entry.options)
            opts["profiles"] = allp
            self.hass.config_entries.async_update_entry(entry, options=opts)

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
            return None

        mode = src.get("mode")

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
                if clone_from and clone_from in (options.get("profiles") or {}):
                    other = options["profiles"][clone_from]
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
                ai = src.get("ai", {}) or {}
                ttl_h = int(ai.get("ttl_hours", 720))
                last_run = ai.get("last_run")
                if last_run:
                    ts = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    if datetime.now(UTC) - ts < timedelta(hours=ttl_h):
                        prof = options.get("profiles", {}).get(profile_id, {})
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
                    ai_args=src.get("ai"),
                )
                if result is not None:
                    ai_meta = src.get("ai", {}) or {}
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

    def _update_ai_cache(self, entry, pid, key, val, conf, notes, links):
        opts = dict(entry.options)
        prof = dict(opts.get("profiles", {}).get(pid, {}))
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
        allp = dict(opts.get("profiles", {}))
        allp[pid] = prof
        opts["profiles"] = allp
        self.hass.config_entries.async_update_entry(entry, options=opts)


async def generate_profile(
    hass: HomeAssistant,
    entry,
    profile_id: str,
    mode: str,
    source_profile_id: str | None = None,
) -> None:
    """Populate all variables for a profile from a single source and resolve immediately."""

    opts = dict(entry.options)
    prof = dict(opts.get("profiles", {}).get(profile_id, {}))
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
        other = dict(opts.get("profiles", {}).get(source_profile_id, {}))
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
    allp = dict(opts.get("profiles", {}))
    allp[profile_id] = prof
    opts["profiles"] = allp
    hass.config_entries.async_update_entry(entry, options=opts)

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
