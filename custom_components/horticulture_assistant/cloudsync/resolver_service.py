from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ..profile.schema import (
    Citation,
    ComputedStatSnapshot,
    FieldAnnotation,
    PlantProfile,
    ProfileComputedSection,
    ProfileLibrarySection,
    ProfileLineageEntry,
    ProfileLocalSection,
    ProfileResolvedSection,
    ProfileSections,
    ResolvedTarget,
)
from .edge_store import EdgeSyncStore

try:
    UTC = datetime.UTC  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Python <3.11 fallback
    UTC = timezone.utc  # noqa: UP017


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


@dataclass(slots=True)
class ResolveAnnotations:
    """Describes how a value was produced and whether supporting data is fresh."""

    source_type: str
    source_ref: list[str] = field(default_factory=list)
    method: str | None = None
    confidence: float | None = None
    staleness_days: float | None = None
    is_stale: bool = False
    overlay_source_type: str | None = None
    overlay_source_ref: list[str] = field(default_factory=list)
    overlay_method: str | None = None


@dataclass(slots=True)
class ResolveResult:
    value: Any
    provenance: list[str]
    overlay: Any | None
    overlay_provenance: list[str]
    staleness_days: float | None
    annotations: ResolveAnnotations


class EdgeResolverService:
    """Resolve profile fields using cached cloud data with offline fallbacks."""

    def __init__(
        self,
        store: EdgeSyncStore,
        *,
        local_profile_loader: Callable[[str], dict[str, Any]] | None = None,
        fallback_provider: Callable[[str], Any] | None = None,
        stats_ttl: timedelta | None = None,
    ) -> None:
        self.store = store
        self.local_profile_loader = local_profile_loader or (lambda _pid: {})
        self.fallback_provider = fallback_provider or (lambda _field: None)
        self.stats_ttl = stats_ttl or timedelta(days=30)

    # ------------------------------------------------------------------
    def resolve_field(self, profile_id: str, field_path: str, *, now: datetime | None = None) -> ResolveResult:
        now = now or datetime.now(tz=UTC)
        lineage = self._load_lineage(profile_id)
        provenance: list[str] = []
        value: Any = None
        found = False
        source_type = "default"
        source_ref: list[str] = []
        method = "default"
        confidence: float | None = None

        for entry in lineage:
            local_found = False
            for candidate in self._iter_local_candidates(entry.local_overrides):
                local_value = self._extract(candidate, field_path)
                if local_value is not None:
                    value = local_value
                    provenance.append(f"local:{entry.profile_id}")
                    source_type = "local_override"
                    source_ref = [entry.profile_id]
                    method = "inheritance"
                    confidence = 1.0
                    found = True
                    local_found = True
                    break
            if local_found:
                break
            curated = self._extract(entry.cloud_payload.get("curated_targets", {}), field_path)
            if curated is not None:
                value = curated
                provenance.append(f"curated:{entry.profile_id}")
                source_type = "curated"
                source_ref = [entry.profile_id]
                method = "inheritance"
                confidence = 0.9
                found = True
                break
            diffs = self._extract(entry.cloud_payload.get("diffs_vs_parent", {}), field_path)
            if diffs is not None:
                value = diffs
                provenance.append(f"override:{entry.profile_id}")
                source_type = "override"
                source_ref = [entry.profile_id]
                method = "inheritance"
                confidence = 0.8
                found = True
                break

        if not found:
            fallback = self.fallback_provider(field_path)
            if fallback is not None:
                value = fallback
                provenance.append("fallback:system")
                source_type = "fallback"
                source_ref = ["system"]
                method = "fallback"
                confidence = 0.5
            else:
                provenance.append("default:none")
                source_type = "default"
                source_ref = []
                method = "default"
                confidence = None

        overlay, overlay_meta = self._resolve_overlay(lineage, field_path, now)
        staleness_days = overlay_meta.get("staleness_days")
        annotations = ResolveAnnotations(
            source_type=source_type,
            source_ref=source_ref,
            method=method,
            confidence=confidence,
            staleness_days=staleness_days,
            is_stale=overlay_meta.get("is_stale", False),
            overlay_source_type=overlay_meta.get("source_type"),
            overlay_source_ref=overlay_meta.get("source_ref", []),
            overlay_method=overlay_meta.get("method"),
        )

        return ResolveResult(
            value=value,
            provenance=provenance,
            overlay=overlay,
            overlay_provenance=overlay_meta.get("provenance", []),
            staleness_days=staleness_days,
            annotations=annotations,
        )

    def resolve_many(
        self, profile_id: str, fields: Iterable[str], *, now: datetime | None = None
    ) -> dict[str, ResolveResult]:
        results: dict[str, ResolveResult] = {}
        for field_name in fields:
            results[field_name] = self.resolve_field(profile_id, field_name, now=now)
        return results

    def resolve_target(
        self,
        profile_id: str,
        field_path: str,
        *,
        now: datetime | None = None,
    ) -> ResolvedTarget:
        result = self.resolve_field(profile_id, field_path, now=now)
        return resolve_result_to_resolved_target(result)

    def resolve_profile(
        self,
        profile_id: str,
        *,
        now: datetime | None = None,
        fields: Iterable[str] | None = None,
        local_payload: Mapping[str, Any] | None = None,
    ) -> PlantProfile:
        """Resolve all relevant fields for ``profile_id``."""

        now = now or datetime.now(tz=UTC)
        lineage = self._load_lineage(profile_id)
        if not lineage:
            raise ValueError(f"unknown profile {profile_id}")
        subject = lineage[0]

        library_payload = dict(subject.cloud_payload)
        library_payload.setdefault("profile_id", profile_id)
        library = ProfileLibrarySection.from_json(library_payload, fallback_id=profile_id)

        local_payload_obj = subject.local_overrides if local_payload is None else local_payload
        local_payload_map = dict(local_payload_obj) if isinstance(local_payload_obj, Mapping) else {}
        local = ProfileLocalSection.from_json(local_payload_map)

        species_id = lineage[-1].profile_id
        stats_payload = self.store.fetch_cloud_cache("computed", species_id)
        computed_snapshot = (
            ComputedStatSnapshot.from_json(stats_payload) if isinstance(stats_payload, Mapping) else None
        )

        target_fields: set[str] = set(fields or [])
        candidate_maps: list[Mapping[str, Any] | None] = [
            library.curated_targets,
            library.diffs_vs_parent,
            local.local_overrides,
        ]
        if computed_snapshot:
            candidate_maps.append(computed_snapshot.payload)
        for mapping in candidate_maps:
            target_fields.update(self._collect_target_fields(mapping))
        if not target_fields:
            resolved_keys = local.resolver_state.get("resolved_keys")
            if isinstance(resolved_keys, Iterable):
                for key in resolved_keys:
                    key_str = str(key)
                    if self._allowed_field(key_str):
                        target_fields.add(key_str)

        resolved_targets: dict[str, ResolvedTarget] = {}
        for field_path in sorted(target_fields):
            result = self.resolve_field(profile_id, field_path, now=now)
            resolved_targets[field_path] = resolve_result_to_resolved_target(result)

        citations = [Citation(**asdict(cit)) for cit in local.citations]
        computed_stats = [computed_snapshot] if computed_snapshot else []

        display_name = (
            (local.general.get("name") if isinstance(local.general, Mapping) else None)
            or library.identity.get("name")
            or library.identity.get("common_name")
            or profile_id
        )

        species = local.species
        if species is None:
            taxonomy_species = library.taxonomy.get("species")
            if isinstance(taxonomy_species, str):
                species = taxonomy_species

        resolved_section = ProfileResolvedSection(
            thresholds={key: target.value for key, target in resolved_targets.items()},
            resolved_targets=resolved_targets,
            variables={key: target.to_legacy() for key, target in resolved_targets.items()},
            citation_map=_coerce_dict((local.metadata or {}).get("citation_map")),
            metadata=dict(local.metadata),
            last_resolved=local.last_resolved,
        )

        computed_metadata: dict[str, Any] = {}
        if computed_snapshot and computed_snapshot.computed_at:
            computed_at_dt = datetime.fromisoformat(str(computed_snapshot.computed_at).replace("Z", "+00:00"))
            staleness = now - computed_at_dt
            computed_metadata["computed_at"] = computed_snapshot.computed_at
            computed_metadata["staleness_days"] = staleness.total_seconds() / 86400
            if self.stats_ttl and staleness > self.stats_ttl:
                computed_metadata["is_stale"] = True

        computed_section = ProfileComputedSection(
            snapshots=[computed_snapshot] if computed_snapshot else [],
            latest=computed_snapshot,
            contributions=list(computed_snapshot.contributions) if computed_snapshot else [],
            metadata=computed_metadata,
        )

        profile = PlantProfile(
            plant_id=profile_id,
            display_name=str(display_name),
            profile_type=library.profile_type,
            species=species,
            tenant_id=library.tenant_id,
            parents=list(library.parents),
            identity=dict(library.identity),
            taxonomy=dict(library.taxonomy),
            policies=dict(library.policies),
            stable_knowledge=dict(library.stable_knowledge),
            lifecycle=dict(library.lifecycle),
            traits=dict(library.traits),
            tags=list(library.tags),
            curated_targets=dict(library.curated_targets),
            diffs_vs_parent=dict(library.diffs_vs_parent),
            library_metadata=dict(library.metadata),
            library_created_at=library.created_at,
            library_updated_at=library.updated_at,
            local_overrides=dict(local.local_overrides),
            resolver_state=dict(local.resolver_state),
            resolved_targets=resolved_targets,
            computed_stats=computed_stats,
            general=dict(local.general),
            citations=citations,
            local_metadata=dict(local.metadata),
            last_resolved=local.last_resolved,
            created_at=local.created_at,
            updated_at=local.updated_at,
            sections=ProfileSections(
                library=library,
                local=local,
                resolved=resolved_section,
                computed=computed_section,
            ),
        )

        profile.lineage = [self._lineage_entry(entry) for entry in lineage]

        return profile

    # ------------------------------------------------------------------
    def _load_lineage(self, profile_id: str) -> list[LineageEntry]:
        lineage: list[LineageEntry] = []
        queue: list[tuple[str, int]] = [(profile_id, 0)]
        visited: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            cloud_payload = self.store.fetch_cloud_cache("profile", current) or {}
            local_payload = self.local_profile_loader(current) or {}
            lineage.append(
                LineageEntry(
                    profile_id=current,
                    depth=depth,
                    cloud_payload=cloud_payload,
                    local_overrides=local_payload,
                )
            )
            parents = cloud_payload.get("parents")
            if isinstance(parents, list):
                for parent in parents:
                    parent_id = str(parent)
                    if parent_id not in visited:
                        queue.append((parent_id, depth + 1))
        lineage.sort(key=lambda entry: entry.depth)
        return lineage

    def _lineage_entry(self, entry: LineageEntry) -> ProfileLineageEntry:
        cloud = entry.cloud_payload or {}
        parents_raw = cloud.get("parents") or []
        parents = [parents_raw] if isinstance(parents_raw, str) else [str(item) for item in parents_raw]
        tags_raw = cloud.get("tags") or []
        tags = [tags_raw] if isinstance(tags_raw, str) else [str(item) for item in tags_raw]
        return ProfileLineageEntry(
            profile_id=entry.profile_id,
            profile_type=str(cloud.get("profile_type", "line")),
            depth=entry.depth,
            role="self" if entry.depth == 0 else "ancestor",
            tenant_id=cloud.get("tenant_id"),
            parents=parents,
            tags=tags,
            identity=_coerce_dict(cloud.get("identity")),
            taxonomy=_coerce_dict(cloud.get("taxonomy")),
            policies=_coerce_dict(cloud.get("policies")),
            stable_knowledge=_coerce_dict(cloud.get("stable_knowledge")),
            lifecycle=_coerce_dict(cloud.get("lifecycle")),
            traits=_coerce_dict(cloud.get("traits")),
            curated_targets=_coerce_dict(cloud.get("curated_targets")),
            diffs_vs_parent=_coerce_dict(cloud.get("diffs_vs_parent")),
            metadata=_coerce_dict(cloud.get("metadata")),
            created_at=cloud.get("created_at"),
            updated_at=cloud.get("updated_at"),
        )

    def _iter_local_candidates(self, payload: Any) -> Iterable[Mapping[str, Any]]:
        if isinstance(payload, Mapping):
            yield payload
            for key in ("local_overrides", "curated_targets", "diffs_vs_parent", "overrides"):
                nested = payload.get(key)
                if isinstance(nested, Mapping):
                    yield nested

    def _resolve_overlay(
        self,
        lineage: list[LineageEntry],
        field_path: str,
        now: datetime,
    ) -> tuple[Any | None, dict[str, Any]]:
        if not lineage:
            return None, {"provenance": []}
        species_id = lineage[-1].profile_id
        stats_payload = self.store.fetch_cloud_cache("computed", species_id)
        if not stats_payload:
            return None, {"provenance": []}
        computed_at_raw = stats_payload.get("computed_at")
        staleness_days: float | None = None
        is_stale = False
        if computed_at_raw:
            computed_at = datetime.fromisoformat(str(computed_at_raw).replace("Z", "+00:00"))
            staleness = now - computed_at
            staleness_days = staleness.total_seconds() / 86400
            if self.stats_ttl and staleness > self.stats_ttl:
                is_stale = True
        overlay = self._extract(stats_payload.get("payload", {}), field_path)
        provenance = [f"computed:{species_id}"] if overlay is not None else []
        meta = {
            "provenance": provenance,
            "staleness_days": staleness_days,
            "is_stale": is_stale,
            "source_type": "computed_stats" if overlay is not None else None,
            "source_ref": [species_id] if overlay is not None else [],
            "method": "data_driven" if overlay is not None else None,
        }
        return overlay, meta

    def _extract(self, payload: Any, field_path: str) -> Any:
        if not isinstance(payload, dict):
            return None
        current: Any = payload
        for part in field_path.split('.'):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _collect_target_fields(self, payload: Any, prefix: str = "") -> set[str]:
        results: set[str] = set()
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                key_str = str(key)
                next_prefix = f"{prefix}.{key_str}" if prefix else key_str
                if isinstance(value, Mapping):
                    if prefix or self._allowed_field(next_prefix):
                        results.update(self._collect_target_fields(value, next_prefix))
                else:
                    if self._allowed_field(next_prefix):
                        results.add(next_prefix)
        elif prefix and self._allowed_field(prefix):
            results.add(prefix)
        return results

    def _allowed_field(self, field_path: str) -> bool:
        return field_path.startswith(("targets", "thresholds", "setpoints"))


@dataclass(slots=True)
class LineageEntry:
    profile_id: str
    depth: int
    cloud_payload: dict[str, Any]
    local_overrides: dict[str, Any]


def resolve_result_to_annotation(result: ResolveResult) -> FieldAnnotation:
    annotations = result.annotations
    extras: dict[str, Any] = {}
    if result.provenance:
        extras["provenance"] = list(result.provenance)
    if annotations.overlay_source_type:
        extras.setdefault("overlay_source", annotations.overlay_source_type)
    if annotations.overlay_source_ref:
        extras.setdefault("overlay_source_ref", list(annotations.overlay_source_ref))
    annotation = FieldAnnotation(
        source_type=annotations.source_type or "unknown",
        source_ref=list(annotations.source_ref),
        method=annotations.method,
        confidence=annotations.confidence,
        staleness_days=annotations.staleness_days,
        is_stale=annotations.is_stale,
        overlay=result.overlay,
        overlay_provenance=list(result.overlay_provenance or []),
        overlay_source_type=annotations.overlay_source_type,
        overlay_source_ref=list(annotations.overlay_source_ref),
        overlay_method=annotations.overlay_method,
        extras=extras,
    )
    return annotation


def resolve_result_to_resolved_target(result: ResolveResult) -> ResolvedTarget:
    annotation = resolve_result_to_annotation(result)
    return ResolvedTarget(value=result.value, annotation=annotation, citations=[])
