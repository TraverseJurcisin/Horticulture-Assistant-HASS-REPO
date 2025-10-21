"""Helpers for converting config entry profile options into dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..const import CONF_PROFILE_SCOPE
from .schema import (
    Citation,
    ComputedStatSnapshot,
    FieldAnnotation,
    PlantProfile,
    ResolvedTarget,
)
from .schema import ProfileLibrarySection, ProfileLocalSection
from .utils import ensure_sections


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _merge_dict(base: Any, overlay: Any) -> dict[str, Any]:
    merged = _as_dict(base)
    merged.update(_as_dict(overlay))
    return merged


def _merge_section_metadata(
    section: ProfileLibrarySection | ProfileLocalSection,
    fallbacks: Mapping[str, Any] | None,
) -> dict[str, Any]:
    metadata = dict(getattr(section, "metadata", {}) or {})
    if fallbacks:
        for key, value in fallbacks.items():
            metadata.setdefault(str(key), value)
    return metadata


def options_profile_to_dataclass(
    profile_id: str,
    payload: Mapping[str, Any],
    *,
    display_name: str | None = None,
) -> PlantProfile:
    """Build a :class:`PlantProfile` from config entry options payload."""

    options = dict(payload)
    name = display_name or options.get("name") or profile_id
    library_section, local_section = ensure_sections(
        options,
        plant_id=profile_id,
        display_name=name,
    )
    library_payload = library_section.to_json()
    local_payload = local_section.to_json()

    sources = options.get("sources") or {}
    citations_map = options.get("citations") or {}

    thresholds = options.get("thresholds") or {}
    resolved_targets: dict[str, ResolvedTarget] = {}
    for key, value in _as_dict(thresholds).items():
        source_details = sources.get(key, {}) if isinstance(sources, Mapping) else {}
        mode = str(source_details.get("mode", "manual")) if source_details else "manual"
        annotation = FieldAnnotation(source_type=mode, method=mode)

        if isinstance(source_details, Mapping):
            if mode == "clone":
                ref = source_details.get("copy_from")
                if ref:
                    annotation.source_ref = [str(ref)]
            elif mode == "opb":
                opb = source_details.get("opb", {})
                species = opb.get("species")
                field = opb.get("field")
                if species:
                    annotation.source_ref = [str(species)]
                extras: dict[str, Any] = {}
                if field:
                    extras["field"] = field
                if extras:
                    annotation.extras.update(extras)
            elif mode == "ai":
                ai_meta = source_details.get("ai", {})
                if isinstance(ai_meta, Mapping):
                    annotation.confidence = ai_meta.get("confidence")
                    model = ai_meta.get("model") or ai_meta.get("provider")
                    if model:
                        annotation.method = str(model)
                    ttl = ai_meta.get("ttl_hours")
                    if ttl is not None:
                        annotation.extras.setdefault("ttl_hours", ttl)
                    notes = ai_meta.get("notes")
                    if notes:
                        annotation.extras.setdefault("notes", notes)
                    links = ai_meta.get("links")
                    if links:
                        annotation.extras.setdefault("links", links)
            annotation.extras.setdefault("raw_source", dict(source_details))

        citations: list[Citation] = []
        cit_data = citations_map.get(key)
        if isinstance(cit_data, Mapping):
            annotation.extras.setdefault("source_detail", cit_data.get("source_detail"))
            citations.append(
                Citation(
                    source=str(cit_data.get("mode", mode)),
                    title=str(cit_data.get("source_detail", "")),
                    details={"source_detail": cit_data.get("source_detail", "")},
                    accessed=str(cit_data.get("ts")) if cit_data.get("ts") else None,
                )
            )

        resolved_targets[str(key)] = ResolvedTarget(
            value=value,
            annotation=annotation,
            citations=citations,
        )

    existing_resolved = options.get("resolved_targets") or {}
    if isinstance(existing_resolved, Mapping):
        for key, payload in existing_resolved.items():
            if str(key) in resolved_targets:
                continue
            if isinstance(payload, Mapping):
                resolved_targets[str(key)] = ResolvedTarget.from_json(dict(payload))

    variables = options.get("variables") or {}
    if isinstance(variables, Mapping):
        for key, value in variables.items():
            key_str = str(key)
            if key_str in resolved_targets:
                continue
            if isinstance(value, Mapping) and "value" in value:
                annotation = (
                    FieldAnnotation.from_json(value.get("annotation", {}))
                    if isinstance(value.get("annotation"), Mapping)
                    else FieldAnnotation(source_type=str(value.get("source", "manual")))
                )
                resolved_targets[key_str] = ResolvedTarget(
                    value=value.get("value"),
                    annotation=annotation,
                    citations=[Citation(**item) for item in value.get("citations", []) if isinstance(item, Mapping)],
                )

    general: dict[str, Any] = {}
    if isinstance(options.get("general"), Mapping):
        general.update(dict(options["general"]))

    sensors = options.get("sensors")
    if isinstance(sensors, Mapping):
        general.setdefault("sensors", dict(sensors))

    scope = options.get(CONF_PROFILE_SCOPE) or options.get("scope")
    if scope is not None:
        general[CONF_PROFILE_SCOPE] = scope

    template = options.get("template")
    if template is not None:
        general.setdefault("template", template)

    if isinstance(local_payload.get("general"), Mapping):
        general.update(local_payload["general"])

    computed_stats = [
        ComputedStatSnapshot.from_json(item)
        for item in options.get("computed_stats", []) or []
        if isinstance(item, Mapping)
    ]

    profile_citations = [
        Citation(**item)
        for item in options.get("profile_citations", [])
        if isinstance(item, Mapping)
    ]
    local_citations_payload = local_payload.get("citations")
    if isinstance(local_citations_payload, list):
        for item in local_citations_payload:
            if isinstance(item, Mapping):
                profile_citations.append(Citation(**item))

    parents = _coerce_str_list(options.get("parents"))
    if not parents:
        parents = _coerce_str_list(library_payload.get("parents"))

    tags = _coerce_str_list(options.get("tags"))
    if not tags:
        tags = _coerce_str_list(library_payload.get("tags"))

    profile_type = str(library_payload.get("profile_type") or options.get("profile_type", "line"))
    species = (
        local_payload.get("species")
        if local_payload.get("species") is not None
        else options.get("species")
    )
    tenant_id = (
        library_payload.get("tenant_id")
        if library_payload.get("tenant_id") is not None
        else options.get("tenant_id")
    )

    identity = _merge_dict(options.get("identity"), library_payload.get("identity"))
    taxonomy = _merge_dict(options.get("taxonomy"), library_payload.get("taxonomy"))
    policies = _merge_dict(options.get("policies"), library_payload.get("policies"))
    stable_knowledge = _merge_dict(options.get("stable_knowledge"), library_payload.get("stable_knowledge"))
    lifecycle = _merge_dict(options.get("lifecycle"), library_payload.get("lifecycle"))
    traits = _merge_dict(options.get("traits"), library_payload.get("traits"))
    curated_targets = _merge_dict(options.get("curated_targets"), library_payload.get("curated_targets"))
    diffs_vs_parent = _merge_dict(options.get("diffs_vs_parent"), library_payload.get("diffs_vs_parent"))

    local_overrides = _merge_dict(local_payload.get("local_overrides"), options.get("local_overrides"))
    resolver_state = _merge_dict(local_payload.get("resolver_state"), options.get("resolver_state"))

    library_metadata = _merge_section_metadata(library_section, options.get("library_metadata"))
    local_metadata = _merge_section_metadata(local_section, options.get("local_metadata"))

    library_created_at = library_payload.get("created_at") or options.get("library_created_at")
    library_updated_at = library_payload.get("updated_at") or options.get("library_updated_at")
    last_resolved = local_payload.get("last_resolved") or options.get("last_resolved")
    created_at = local_payload.get("created_at") or options.get("created_at")
    updated_at = local_payload.get("updated_at") or options.get("updated_at")

    profile = PlantProfile(
        plant_id=profile_id,
        display_name=name,
        profile_type=profile_type,
        species=species,
        tenant_id=tenant_id,
        parents=parents,
        identity=identity,
        taxonomy=taxonomy,
        policies=policies,
        stable_knowledge=stable_knowledge,
        lifecycle=lifecycle,
        traits=traits,
        tags=tags,
        curated_targets=curated_targets,
        diffs_vs_parent=diffs_vs_parent,
        library_metadata=library_metadata,
        library_created_at=library_created_at,
        library_updated_at=library_updated_at,
        local_overrides=local_overrides,
        resolver_state=resolver_state,
        resolved_targets=resolved_targets,
        computed_stats=computed_stats,
        general=general,
        citations=profile_citations,
        local_metadata=local_metadata,
        last_resolved=last_resolved,
        created_at=created_at,
        updated_at=updated_at,
    )

    return profile

__all__ = [
    "options_profile_to_dataclass",
]

