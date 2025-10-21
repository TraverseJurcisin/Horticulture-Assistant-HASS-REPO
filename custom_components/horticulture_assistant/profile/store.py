from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import CONF_PROFILE_SCOPE
from .schema import (
    Citation,
    ComputedStatSnapshot,
    FieldAnnotation,
    PlantProfile,
    ResolvedTarget,
)

STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_profiles"


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    return await _store(hass).async_load() or {}


async def async_save_profile(hass: HomeAssistant, profile: PlantProfile | dict[str, Any]) -> None:
    """Persist a profile dictionary or dataclass to storage."""

    if isinstance(profile, PlantProfile):
        profile = profile.to_json()

    data = await async_load_all(hass)
    data[profile["plant_id"]] = profile
    await _store(hass).async_save(data)


async def async_save_profile_from_options(hass: HomeAssistant, entry, profile_id: str) -> None:
    """Persist a profile from config entry options to storage."""

    prof = entry.options.get("profiles", {}).get(profile_id, {})
    sources = prof.get("sources") or {}
    citations_map = prof.get("citations") or {}
    library_payload = prof.get("library") if isinstance(prof.get("library"), dict) else {}
    local_payload = prof.get("local") if isinstance(prof.get("local"), dict) else {}

    def _dict_copy(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}
    thresholds = prof.get("thresholds") or {}

    resolved_targets: dict[str, ResolvedTarget] = {}
    for key, value in thresholds.items():
        source_details = sources.get(key, {}) if isinstance(sources, dict) else {}
        mode = str(source_details.get("mode", "manual"))
        annotation = FieldAnnotation(source_type=mode, method=mode)

        if mode == "clone":
            ref = source_details.get("copy_from")
            if ref:
                annotation.source_ref = [str(ref)]
        elif mode == "opb":
            opb = source_details.get("opb", {}) if isinstance(source_details, dict) else {}
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
            ai_meta = source_details.get("ai", {}) if isinstance(source_details, dict) else {}
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

        if source_details:
            annotation.extras.setdefault("raw_source", source_details)

        cit_data = citations_map.get(key)
        citations: list[Citation] = []
        if isinstance(cit_data, dict):
            annotation.extras.setdefault("source_detail", cit_data.get("source_detail"))
            citations.append(
                Citation(
                    source=str(cit_data.get("mode", mode)),
                    title=str(cit_data.get("source_detail", "")),
                    details={"source_detail": cit_data.get("source_detail", "")},
                    accessed=cit_data.get("ts"),
                )
            )

        resolved_targets[str(key)] = ResolvedTarget(value=value, annotation=annotation, citations=citations)

    general: dict[str, Any] = {}
    if isinstance(prof.get("general"), dict):
        general.update(prof["general"])

    sensors = prof.get("sensors")
    if isinstance(sensors, dict):
        general["sensors"] = dict(sensors)

    scope = prof.get(CONF_PROFILE_SCOPE) or prof.get("scope")
    if scope is not None:
        general[CONF_PROFILE_SCOPE] = scope

    if isinstance(local_payload.get("general"), dict):
        general.update(local_payload["general"])

    computed_stats = [
        ComputedStatSnapshot.from_json(item)
        for item in prof.get("computed_stats", []) or []
        if isinstance(item, dict)
    ]

    profile_citations = [
        Citation(**item)
        for item in prof.get("profile_citations", [])
        if isinstance(item, dict)
    ]
    if isinstance(local_payload.get("citations"), list):
        for item in local_payload["citations"]:
            if isinstance(item, dict):
                profile_citations.append(Citation(**item))

    parents_raw = prof.get("parents")
    if isinstance(parents_raw, (list, tuple)):
        parents = [str(item) for item in parents_raw]
    elif isinstance(parents_raw, str):
        parents = [parents_raw]
    elif parents_raw is None:
        parents = []
    else:
        parents = [str(parents_raw)]

    lib_parents = library_payload.get("parents")
    if not parents and lib_parents is not None:
        if isinstance(lib_parents, (list, tuple)):
            parents = [str(item) for item in lib_parents]
        else:
            parents = [str(lib_parents)]

    tags_raw = prof.get("tags")
    if isinstance(tags_raw, (list, tuple)):
        tags = [str(item) for item in tags_raw]
    elif isinstance(tags_raw, str):
        tags = [tags_raw]
    elif tags_raw is None:
        tags = []
    else:
        tags = [str(tags_raw)]

    lib_tags = library_payload.get("tags")
    if not tags and lib_tags is not None:
        if isinstance(lib_tags, (list, tuple)):
            tags = [str(item) for item in lib_tags]
        else:
            tags = [str(lib_tags)]

    profile_type = str(library_payload.get("profile_type") or prof.get("profile_type", "line"))
    species = local_payload.get("species") if local_payload.get("species") is not None else prof.get("species")
    tenant_id = library_payload.get("tenant_id") if library_payload.get("tenant_id") is not None else prof.get("tenant_id")

    identity = _dict_copy(prof.get("identity"))
    identity.update(_dict_copy(library_payload.get("identity")))
    taxonomy = _dict_copy(prof.get("taxonomy"))
    taxonomy.update(_dict_copy(library_payload.get("taxonomy")))
    policies = _dict_copy(prof.get("policies"))
    policies.update(_dict_copy(library_payload.get("policies")))
    stable_knowledge = _dict_copy(prof.get("stable_knowledge"))
    stable_knowledge.update(_dict_copy(library_payload.get("stable_knowledge")))
    lifecycle = _dict_copy(prof.get("lifecycle"))
    lifecycle.update(_dict_copy(library_payload.get("lifecycle")))
    traits = _dict_copy(prof.get("traits"))
    traits.update(_dict_copy(library_payload.get("traits")))

    curated_targets = _dict_copy(prof.get("curated_targets"))
    curated_targets.update(_dict_copy(library_payload.get("curated_targets")))
    diffs_vs_parent = _dict_copy(prof.get("diffs_vs_parent"))
    diffs_vs_parent.update(_dict_copy(library_payload.get("diffs_vs_parent")))

    local_overrides = _dict_copy(local_payload.get("local_overrides"))
    if not local_overrides:
        local_overrides = _dict_copy(prof.get("local_overrides"))

    resolver_state = _dict_copy(local_payload.get("resolver_state"))
    if not resolver_state:
        resolver_state = _dict_copy(prof.get("resolver_state"))

    library_metadata = _dict_copy(library_payload.get("metadata"))
    if not library_metadata:
        library_metadata = _dict_copy(prof.get("library_metadata"))

    local_metadata = _dict_copy(local_payload.get("metadata"))
    if not local_metadata:
        local_metadata = _dict_copy(prof.get("local_metadata"))

    library_created_at = library_payload.get("created_at") or prof.get("library_created_at")
    library_updated_at = library_payload.get("updated_at") or prof.get("library_updated_at")
    last_resolved = local_payload.get("last_resolved") or prof.get("last_resolved")
    created_at = local_payload.get("created_at") or prof.get("created_at")
    updated_at = local_payload.get("updated_at") or prof.get("updated_at")

    profile = PlantProfile(
        plant_id=profile_id,
        display_name=prof.get("name", profile_id),
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
    await async_save_profile(hass, profile)


async def async_get_profile(hass: HomeAssistant, plant_id: str) -> dict[str, Any] | None:
    return (await async_load_all(hass)).get(plant_id)


async def async_load_profile(hass: HomeAssistant, plant_id: str) -> PlantProfile | None:
    """Load a PlantProfile dataclass for a given plant ID."""

    data = await async_get_profile(hass, plant_id)
    return PlantProfile.from_json(data) if data else None


async def async_load_profiles(hass: HomeAssistant) -> dict[str, PlantProfile]:
    """Load all stored profiles as dataclasses."""

    data = await async_load_all(hass)
    return {pid: PlantProfile.from_json(p) for pid, p in data.items()}


async def async_delete_profile(hass: HomeAssistant, plant_id: str) -> None:
    data = await async_load_all(hass)
    if plant_id in data:
        del data[plant_id]
        await _store(hass).async_save(data)
