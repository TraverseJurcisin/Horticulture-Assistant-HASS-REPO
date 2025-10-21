from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from ..const import CONF_PROFILE_SCOPE
from .schema import Citation, PlantProfile, ProfileLibrarySection, ProfileLocalSection


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
    if isinstance(general, Mapping):
        general_dict = dict(general)
    else:
        general_dict = {}

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

    profile = PlantProfile.from_json(data)
    library = profile.library_section()
    local = profile.local_section()

    payload["plant_id"] = profile.plant_id
    payload["display_name"] = profile.display_name
    payload["library"] = library.to_json()
    payload["local"] = local.to_json()

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
        fallback_id = _ensure_string(data.get("plant_id") or data.get("profile_id"), "profile")
    data.setdefault("plant_id", fallback_id)
    if display_name is None:
        display_name = data.get("display_name") or data.get("name")
    data.setdefault("display_name", display_name or fallback_id)

    general = data.get("general")
    if isinstance(general, Mapping):
        general_dict = dict(general)
    else:
        general_dict = {}

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

    profile = PlantProfile.from_json(data)
    return profile.to_json()


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


__all__ = [
    "citations_map_to_list",
    "ensure_sections",
    "normalise_profile_payload",
]
