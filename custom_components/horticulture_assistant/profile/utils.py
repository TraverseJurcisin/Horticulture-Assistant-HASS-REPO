from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from ..const import CONF_PROFILE_SCOPE
from .schema import (
    Citation,
    BioProfile,
    ProfileLibrarySection,
    ProfileLocalSection,
    SpeciesProfile,
)


def _ensure_string(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    return str(value)


def ensure_sections(
    payload: MutableMapping[str, Any],
    *,
    plant_id: str | None = None,
    display_name: str | None = None,
) -> tuple[ProfileLibrarySection, ProfileLocalSection]:
    """Ensure ``payload`` contains normalised ``library`` and ``local`` sections."""

    data: dict[str, Any] = dict(payload)
    candidate_id = plant_id or data.get("plant_id") or data.get("profile_id") or data.get("name")
    fallback_id = _ensure_string(candidate_id, "profile")
    data.setdefault("plant_id", fallback_id)
    if display_name is None:
        display_name = data.get("display_name") or data.get("name")
    data.setdefault("display_name", display_name or fallback_id)

    general = data.get("general")
    general_dict = dict(general) if isinstance(general, Mapping) else {}

    sensors = data.get("sensors")
    if isinstance(sensors, Mapping):
        general_dict.setdefault("sensors", dict(sensors))
    scope = data.get(CONF_PROFILE_SCOPE) or data.get("scope")
    if scope is not None:
        general_dict.setdefault(CONF_PROFILE_SCOPE, scope)
    template = data.get("template")
    if template is not None:
        general_dict.setdefault("template", template)
    data["general"] = general_dict

    profile = BioProfile.from_json(data)
    sections = profile.refresh_sections()
    library = sections.library
    local = sections.local

    payload["profile_id"] = profile.profile_id
    payload["plant_id"] = profile.profile_id
    payload["display_name"] = profile.display_name
    payload["library"] = library.to_json()
    payload["local"] = local.to_json()
    payload["sections"] = sections.to_json()

    return library, local


def normalise_profile_payload(
    payload: Mapping[str, Any],
    *,
    fallback_id: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Return a canonical serialisable representation for ``payload``."""

    data = dict(payload)
    if fallback_id is None:
        fallback_id = _ensure_string(data.get("profile_id") or data.get("plant_id"), "profile")
    data.setdefault("profile_id", fallback_id)
    data.setdefault("plant_id", fallback_id)
    if display_name is None:
        display_name = data.get("display_name") or data.get("name")
    data.setdefault("display_name", display_name or fallback_id)

    general = data.get("general")
    general_dict = dict(general) if isinstance(general, Mapping) else {}

    sensors = data.get("sensors")
    if isinstance(sensors, Mapping):
        general_dict.setdefault("sensors", dict(sensors))
    scope = data.get(CONF_PROFILE_SCOPE) or data.get("scope")
    if scope is not None:
        general_dict.setdefault(CONF_PROFILE_SCOPE, scope)
    template = data.get("template")
    if template is not None:
        general_dict.setdefault("template", template)
    data["general"] = general_dict

    profile = BioProfile.from_json(data)
    payload = profile.to_json()
    return payload


def citations_map_to_list(citations_map: Mapping[str, Any]) -> list[Citation]:
    """Convert an options ``citations`` mapping into dataclass instances."""

    items: list[Citation] = []
    for field, meta in citations_map.items():
        if not isinstance(meta, Mapping):
            continue
        details: dict[str, Any] | None = None
        detail_value = meta.get("source_detail")
        if detail_value is not None:
            details = {"field": field, "source_detail": detail_value}
        accessed = meta.get("ts")
        if accessed is not None:
            accessed = str(accessed)
        source = str(meta.get("mode") or meta.get("source") or "manual")
        title = str(detail_value or field)
        items.append(
            Citation(
                source=source,
                title=title,
                details=details,
                accessed=accessed,
            )
        )
    return items


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _extract_species_candidate(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        mapping = _coerce_mapping(value)
        for key in (
            "slug",
            "scientific_name",
            "species",
            "name",
            "id",
            "identifier",
            "value",
        ):
            candidate = mapping.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        # Fall back to nested ``species`` payloads commonly shaped as
        # ``{"taxonomy": {"species": "..."}}``.
        taxonomy = mapping.get("taxonomy")
        if isinstance(taxonomy, Mapping):
            nested = _extract_species_candidate(taxonomy)
            if nested:
                return nested
    return None


def determine_species_slug(
    *,
    library: ProfileLibrarySection | None = None,
    local: ProfileLocalSection | None = None,
    raw: Any = None,
) -> str | None:
    """Return the best species identifier for an options payload."""

    for candidate in (
        getattr(local, "species", None),
        raw,
    ):
        slug = _extract_species_candidate(candidate)
        if slug:
            return slug

    if library is not None:
        identity = _coerce_mapping(library.identity)
        for key in ("slug", "scientific_name", "species", "name"):
            slug = _extract_species_candidate(identity.get(key))
            if slug:
                return slug
        taxonomy = _coerce_mapping(library.taxonomy)
        for key in ("slug", "scientific_name", "species", "binomial"):
            slug = _extract_species_candidate(taxonomy.get(key))
            if slug:
                return slug
    return None


def sync_general_section(
    payload: MutableMapping[str, Any],
    general: Mapping[str, Any],
) -> None:
    """Persist ``general`` metadata while mirroring into the local section."""

    general_map = _coerce_mapping(general)
    payload["general"] = general_map

    local_payload = payload.get("local")
    local_map = local_payload if isinstance(local_payload, MutableMapping) else _coerce_mapping(local_payload)

    existing_general = _coerce_mapping(local_map.get("general"))
    merged_general = dict(existing_general)
    merged_general.update(general_map)
    local_map["general"] = merged_general
    payload["local"] = local_map

    ensure_sections(
        payload,
        plant_id=payload.get("plant_id") or payload.get("profile_id") or payload.get("name"),
        display_name=payload.get("display_name") or payload.get("name"),
    )


def link_species_and_cultivars(profiles: Iterable[BioProfile]) -> None:
    """Backfill species↔cultivar relationships for a collection of profiles."""

    species_map: dict[str, BioProfile] = {}
    for profile in profiles:
        if profile.profile_type == "species":
            species_map[profile.profile_id] = profile
            if isinstance(profile, SpeciesProfile):
                profile.cultivar_ids = []
            else:  # pragma: no cover - safety for partially migrated data
                setattr(profile, "cultivar_ids", [])

    for profile in profiles:
        if profile.profile_type == "species":
            continue

        species_id = profile.species_profile_id
        if not species_id:
            for parent in profile.parents:
                parent_id = str(parent)
                if parent_id in species_map:
                    species_id = parent_id
                    break

        if not species_id or species_id not in species_map:
            continue

        profile.species_profile_id = species_id
        species = species_map[species_id]

        deduped_parents: list[str] = []
        seen_parent: set[str] = set()
        for parent in profile.parents:
            parent_id = str(parent)
            if not parent_id or parent_id in seen_parent:
                continue
            seen_parent.add(parent_id)
            deduped_parents.append(parent_id)
        if species.profile_id not in seen_parent:
            deduped_parents.insert(0, species.profile_id)
        profile.parents = deduped_parents

        cultivar_ids = list(getattr(species, "cultivar_ids", []))
        if profile.profile_id not in cultivar_ids:
            cultivar_ids.append(profile.profile_id)
        setattr(species, "cultivar_ids", cultivar_ids)

    for species in species_map.values():
        cultivar_ids = getattr(species, "cultivar_ids", [])
        if cultivar_ids:
            deduped = list(dict.fromkeys(cultivar_ids))
            setattr(species, "cultivar_ids", deduped)


__all__ = [
    "citations_map_to_list",
    "ensure_sections",
    "normalise_profile_payload",
    "determine_species_slug",
    "link_species_and_cultivars",
    "sync_general_section",
]
