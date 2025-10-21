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

    parents_raw = prof.get("parents")
    if isinstance(parents_raw, (list, tuple)):
        parents = [str(item) for item in parents_raw]
    elif isinstance(parents_raw, str):
        parents = [parents_raw]
    elif parents_raw is None:
        parents = []
    else:
        parents = [str(parents_raw)]

    tags_raw = prof.get("tags")
    if isinstance(tags_raw, (list, tuple)):
        tags = [str(item) for item in tags_raw]
    elif isinstance(tags_raw, str):
        tags = [tags_raw]
    elif tags_raw is None:
        tags = []
    else:
        tags = [str(tags_raw)]

    profile = PlantProfile(
        plant_id=profile_id,
        display_name=prof.get("name", profile_id),
        profile_type=str(prof.get("profile_type", "line")),
        species=prof.get("species"),
        tenant_id=prof.get("tenant_id"),
        parents=parents,
        identity=prof.get("identity") or {},
        taxonomy=prof.get("taxonomy") or {},
        policies=prof.get("policies") or {},
        stable_knowledge=prof.get("stable_knowledge") or {},
        lifecycle=prof.get("lifecycle") or {},
        traits=prof.get("traits") or {},
        tags=tags,
        curated_targets=prof.get("curated_targets") or {},
        diffs_vs_parent=prof.get("diffs_vs_parent") or {},
        local_overrides=prof.get("local_overrides") or {},
        resolver_state=prof.get("resolver_state") or {},
        resolved_targets=resolved_targets,
        computed_stats=computed_stats,
        general=general,
        citations=profile_citations,
        last_resolved=prof.get("last_resolved"),
        created_at=prof.get("created_at"),
        updated_at=prof.get("updated_at"),
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
