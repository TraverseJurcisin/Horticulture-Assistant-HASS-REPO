from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from .schema import FieldAnnotation, ResolvedTarget


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` as a mutable dictionary."""

    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def ensure_profile_sections(
    profile: MutableMapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Ensure ``profile`` contains mutable threshold, resolved, and variable maps."""

    thresholds = _coerce_dict(profile.get("thresholds"))
    profile["thresholds"] = thresholds

    resolved = _coerce_dict(profile.get("resolved_targets"))
    profile["resolved_targets"] = resolved

    variables = _coerce_dict(profile.get("variables"))
    profile["variables"] = variables

    return thresholds, resolved, variables


def set_resolved_target(
    profile: MutableMapping[str, Any],
    key: str,
    target: ResolvedTarget,
) -> None:
    """Persist ``target`` into ``profile`` keeping compatibility views in sync."""

    thresholds, resolved, variables = ensure_profile_sections(profile)
    key = str(key)

    if not target.annotation.source_type:
        target.annotation.source_type = "manual"
    if target.annotation.method is None:
        target.annotation.method = target.annotation.source_type

    thresholds[key] = target.value
    resolved[key] = target.to_json()
    variables[key] = target.to_legacy()


def remove_resolved_target(profile: MutableMapping[str, Any], key: str) -> None:
    """Remove ``key`` from all threshold views within ``profile``."""

    thresholds, resolved, variables = ensure_profile_sections(profile)
    key = str(key)
    thresholds.pop(key, None)
    resolved.pop(key, None)
    variables.pop(key, None)


def sync_thresholds(
    profile: MutableMapping[str, Any],
    *,
    default_source: str = "manual",
    touched_keys: Iterable[str] | None = None,
    prune: bool | None = None,
) -> None:
    """Backfill ``resolved_targets`` and ``variables`` from ``thresholds``."""

    thresholds, resolved, variables = ensure_profile_sections(profile)

    if touched_keys is None:
        keys = list(thresholds.keys())
        prune_missing = True if prune is None else prune
    else:
        keys = [str(key) for key in touched_keys]
        prune_missing = False if prune is None else prune

    for key in keys:
        if key not in thresholds:
            if prune_missing:
                resolved.pop(key, None)
                variables.pop(key, None)
            continue
        existing = resolved.get(key)
        if isinstance(existing, ResolvedTarget):
            target = existing
        elif isinstance(existing, Mapping):
            target = ResolvedTarget.from_json(dict(existing))
        else:
            target = ResolvedTarget(
                value=None,
                annotation=FieldAnnotation(source_type=default_source, method=default_source),
                citations=[],
            )
        target.value = thresholds[key]
        if not target.annotation.source_type:
            target.annotation.source_type = default_source
        if target.annotation.method is None:
            target.annotation.method = target.annotation.source_type
        set_resolved_target(profile, key, target)

    if prune_missing:
        for key in list(resolved.keys()):
            if key not in thresholds:
                resolved.pop(key, None)
                variables.pop(key, None)


def get_resolved_target(profile: Mapping[str, Any] | Any, key: str) -> ResolvedTarget | None:
    """Return :class:`ResolvedTarget` for ``key`` from ``profile`` if present."""

    target_map: Any
    if isinstance(profile, Mapping):
        target_map = profile.get("resolved_targets")
    else:
        target_map = getattr(profile, "resolved_targets", None)

    if isinstance(target_map, Mapping):
        value = target_map.get(key)
    else:
        value = None

    if isinstance(value, ResolvedTarget):
        return value
    if isinstance(value, Mapping):
        return ResolvedTarget.from_json(dict(value))
    return None
