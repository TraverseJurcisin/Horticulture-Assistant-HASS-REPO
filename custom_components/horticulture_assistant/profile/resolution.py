"""Helpers for resolving profile values via local inheritance chains."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..const import OPB_FIELD_MAP
from .schema import BioProfile, Citation, FieldAnnotation, ResolvedTarget


@dataclass(slots=True)
class InheritanceResolution:
    """Result returned when a value is located via inheritance."""

    value: Any
    source_profile_id: str
    source_profile_type: str
    source_display_name: str
    depth: int
    chain: list[str]
    reason: str
    origin: ResolvedTarget | None
    provenance: list[dict[str, str]]


def _is_scalar(value: Any) -> bool:
    return value is not None and not isinstance(value, Mapping | set | tuple | list)


def _walk_path(mapping: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        if key not in current:
            return None
        current = current[key]
    return current


def _extract_from_mapping(mapping: Mapping[str, Any] | None, key: str) -> Any:
    if not mapping:
        return None
    if key in mapping:
        return mapping[key]
    path = OPB_FIELD_MAP.get(key)
    if path:
        value = _walk_path(mapping, path.split("."))
        if _is_scalar(value):
            return value
    for value in mapping.values():
        if isinstance(value, Mapping):
            found = _extract_from_mapping(value, key)
            if _is_scalar(found):
                return found
    return None


def _make_origin_target(value: Any, *, source_type: str, method: str, profile_id: str) -> ResolvedTarget:
    return ResolvedTarget(
        value=value,
        annotation=FieldAnnotation(
            source_type=source_type,
            source_ref=[profile_id],
            method=method,
        ),
        citations=[],
    )


def _iter_parent_ids(profile: BioProfile) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    if profile.species_profile_id:
        species_id = str(profile.species_profile_id)
        if species_id and species_id not in seen:
            seen.add(species_id)
            result.append(species_id)
    for parent in profile.parents:
        parent_id = str(parent)
        if parent_id and parent_id not in seen:
            seen.add(parent_id)
            result.append(parent_id)
    return result


def _candidate_value(profile: BioProfile, key: str) -> tuple[Any | None, str, ResolvedTarget | None]:
    value = _extract_from_mapping(profile.local_overrides, key)
    if _is_scalar(value):
        return (
            value,
            "local_overrides",
            _make_origin_target(
                value,
                source_type="local_override",
                method="inheritance",
                profile_id=profile.profile_id,
            ),
        )

    target = profile.resolved_targets.get(key)
    if target is not None:
        return target.value, "resolved_target", target

    thresholds = profile.resolved_section().thresholds
    if key in thresholds and _is_scalar(thresholds[key]):
        value = thresholds[key]
        return (
            value,
            "resolved_threshold",
            _make_origin_target(
                value,
                source_type="resolved",
                method="inheritance",
                profile_id=profile.profile_id,
            ),
        )

    value = _extract_from_mapping(profile.diffs_vs_parent, key)
    if _is_scalar(value):
        return (
            value,
            "diffs_vs_parent",
            _make_origin_target(
                value,
                source_type="diffs_vs_parent",
                method="inheritance",
                profile_id=profile.profile_id,
            ),
        )

    value = _extract_from_mapping(profile.curated_targets, key)
    if _is_scalar(value):
        return (
            value,
            "curated_targets",
            _make_origin_target(
                value,
                source_type="curated",
                method="inheritance",
                profile_id=profile.profile_id,
            ),
        )

    library_curated = profile.library_section().curated_targets
    value = _extract_from_mapping(library_curated, key)
    if _is_scalar(value):
        return (
            value,
            "library_curated",
            _make_origin_target(
                value,
                source_type="curated_library",
                method="inheritance",
                profile_id=profile.profile_id,
            ),
        )

    return None, "unknown", None


def resolve_inheritance_target(
    profile: BioProfile,
    key: str,
    profiles_by_id: Mapping[str, BioProfile],
) -> InheritanceResolution | None:
    """Return an inheritance-based resolution for ``key`` or ``None``."""

    visited: set[str] = set()

    def traverse(current: BioProfile, depth: int, chain: list[str]) -> InheritanceResolution | None:
        current_id = str(current.profile_id)
        if not current_id or current_id in visited:
            return None
        visited.add(current_id)
        next_chain = chain + [current_id]

        value, reason, origin = _candidate_value(current, key)
        if _is_scalar(value):
            provenance: list[dict[str, str]] = []
            for pid in next_chain:
                ref = profiles_by_id.get(pid)
                provenance.append(
                    {
                        "profile_id": pid,
                        "profile_type": ref.profile_type if ref else "unknown",
                        "display_name": ref.display_name if ref else pid,
                    }
                )
            return InheritanceResolution(
                value=value,
                source_profile_id=current.profile_id,
                source_profile_type=current.profile_type,
                source_display_name=current.display_name,
                depth=depth,
                chain=next_chain,
                reason=reason,
                origin=origin,
                provenance=provenance,
            )

        for parent_id in _iter_parent_ids(current):
            parent = profiles_by_id.get(parent_id)
            if parent is None:
                continue
            result = traverse(parent, depth + 1, next_chain)
            if result is not None:
                return result
        return None

    return traverse(profile, 0, [])


def build_profiles_index(profiles: Mapping[str, BioProfile] | Sequence[BioProfile]) -> dict[str, BioProfile]:
    """Return a mapping of profile id to object from ``profiles``."""

    if isinstance(profiles, Mapping):
        return {str(key): value for key, value in profiles.items()}
    return {profile.profile_id: profile for profile in profiles}


def annotate_inherited_target(resolution: InheritanceResolution) -> ResolvedTarget:
    """Return a resolved target with provenance metadata applied."""

    origin = resolution.origin
    citations = []
    overlay_payload = None
    overlay_source_type = None
    overlay_source_ref: list[str] = []
    overlay_method = None
    confidence = None
    staleness_days = None
    is_stale = False
    base_extras: dict[str, Any] = {}

    if origin is not None:
        origin_target = ResolvedTarget(
            value=origin.value,
            annotation=FieldAnnotation.from_json(origin.annotation.to_json()),
            citations=list(origin.citations),
        )
        citations = list(origin_target.citations)
        base_annotation = origin_target.annotation
        overlay_payload = base_annotation.to_json()
        overlay_source_type = base_annotation.source_type
        overlay_source_ref = list(base_annotation.source_ref)
        overlay_method = base_annotation.method
        confidence = base_annotation.confidence
        staleness_days = base_annotation.staleness_days
        is_stale = base_annotation.is_stale
        base_extras = dict(base_annotation.extras or {})
    else:
        base_annotation = FieldAnnotation(
            source_type="inheritance",
            source_ref=[resolution.source_profile_id],
            method="inheritance",
        )

    extras = dict(base_extras)
    extras.update(
        {
            "inheritance_depth": resolution.depth,
            "inheritance_chain": list(resolution.chain),
            "source_profile_id": resolution.source_profile_id,
            "source_profile_type": resolution.source_profile_type,
            "source_profile_name": resolution.source_display_name,
            "inheritance_reason": resolution.reason,
            "provenance": resolution.provenance,
        }
    )

    annotation = FieldAnnotation(
        source_type="inheritance",
        source_ref=list(resolution.chain),
        method="inheritance",
        confidence=confidence,
        staleness_days=staleness_days,
        is_stale=is_stale,
        overlay=overlay_payload,
        overlay_provenance=list(resolution.chain),
        overlay_source_type=overlay_source_type,
        overlay_source_ref=overlay_source_ref,
        overlay_method=overlay_method,
        extras=extras,
    )

    if not any(cit.source == "inheritance" for cit in citations):
        citations.append(
            Citation(
                source="inheritance",
                title=f"Inherited from {resolution.source_display_name}",
                details={
                    "profile_id": resolution.source_profile_id,
                    "profile_type": resolution.source_profile_type,
                },
            )
        )

    return ResolvedTarget(value=resolution.value, annotation=annotation, citations=citations)


__all__ = [
    "InheritanceResolution",
    "annotate_inherited_target",
    "build_profiles_index",
    "resolve_inheritance_target",
]
