from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


SourceType = str  # manual|clone|openplantbook|ai|curated|computed


@dataclass
class Citation:
    source: SourceType
    title: str
    url: str | None = None
    details: dict[str, Any] | None = None
    accessed: str | None = None


@dataclass
class RunEvent:
    """Represents a cultivation run lifecycle event."""

    run_id: str
    profile_id: str
    species_id: str | None
    started_at: str
    ended_at: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "started_at": self.started_at,
        }
        if self.ended_at is not None:
            payload["ended_at"] = self.ended_at
        if self.environment:
            payload["environment"] = dict(self.environment)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> RunEvent:
        return RunEvent(
            run_id=str(data.get("run_id") or data.get("id") or "run"),
            profile_id=str(data.get("profile_id") or data.get("cultivar_id") or ""),
            species_id=(str(data.get("species_id")) if data.get("species_id") else None),
            started_at=str(data.get("started_at") or data.get("start")),
            ended_at=(str(data.get("ended_at")) if data.get("ended_at") else None),
            environment=_as_dict(data.get("environment")),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass
class HarvestEvent:
    """Represents a single harvest outcome."""

    harvest_id: str
    profile_id: str
    species_id: str | None
    run_id: str | None
    harvested_at: str
    yield_grams: float
    area_m2: float | None = None
    wet_weight_grams: float | None = None
    dry_weight_grams: float | None = None
    fruit_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "harvest_id": self.harvest_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "run_id": self.run_id,
            "harvested_at": self.harvested_at,
            "yield_grams": self.yield_grams,
        }
        if self.area_m2 is not None:
            payload["area_m2"] = self.area_m2
        if self.wet_weight_grams is not None:
            payload["wet_weight_grams"] = self.wet_weight_grams
        if self.dry_weight_grams is not None:
            payload["dry_weight_grams"] = self.dry_weight_grams
        if self.fruit_count is not None:
            payload["fruit_count"] = self.fruit_count
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> HarvestEvent:
        area = data.get("area_m2")
        try:
            area_value = float(area) if area is not None else None
        except (TypeError, ValueError):
            area_value = None
        yield_grams = data.get("yield_grams")
        try:
            yield_value = float(yield_grams) if yield_grams is not None else 0.0
        except (TypeError, ValueError):
            yield_value = 0.0
        wet_weight = data.get("wet_weight_grams")
        dry_weight = data.get("dry_weight_grams")
        try:
            wet_value = float(wet_weight) if wet_weight is not None else None
        except (TypeError, ValueError):
            wet_value = None
        try:
            dry_value = float(dry_weight) if dry_weight is not None else None
        except (TypeError, ValueError):
            dry_value = None
        fruit_count = data.get("fruit_count")
        try:
            fruit_value = int(fruit_count) if fruit_count is not None else None
        except (TypeError, ValueError):
            fruit_value = None
        return HarvestEvent(
            harvest_id=str(data.get("harvest_id") or data.get("id") or "harvest"),
            profile_id=str(data.get("profile_id") or data.get("cultivar_id") or ""),
            species_id=(str(data.get("species_id")) if data.get("species_id") else None),
            run_id=(str(data.get("run_id")) if data.get("run_id") else None),
            harvested_at=str(data.get("harvested_at") or data.get("timestamp") or ""),
            yield_grams=yield_value,
            area_m2=area_value,
            wet_weight_grams=wet_value,
            dry_weight_grams=dry_value,
            fruit_count=fruit_value,
            metadata=_as_dict(data.get("metadata")),
        )

    def yield_density(self) -> float | None:
        if not self.area_m2 or self.area_m2 <= 0:
            return None
        return round(self.yield_grams / self.area_m2, 3)


@dataclass
class YieldStatistic:
    """Summarised statistic for a profile or species."""

    stat_id: str
    scope: Literal["species", "cultivar"]
    profile_id: str
    computed_at: str
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stat_id": self.stat_id,
            "scope": self.scope,
            "profile_id": self.profile_id,
            "computed_at": self.computed_at,
            "metrics": dict(self.metrics),
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> YieldStatistic:
        metrics: dict[str, float] = {}
        metric_payload = data.get("metrics")
        if isinstance(metric_payload, Mapping):
            for key, value in metric_payload.items():
                try:
                    metrics[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        return YieldStatistic(
            stat_id=str(data.get("stat_id") or data.get("id") or "stat"),
            scope=str(data.get("scope") or "cultivar"),
            profile_id=str(data.get("profile_id") or ""),
            computed_at=str(data.get("computed_at") or data.get("timestamp") or ""),
            metrics=metrics,
            metadata=_as_dict(data.get("metadata")),
        )

@dataclass
class FieldAnnotation:
    """Metadata describing how a resolved target value was obtained."""

    source_type: SourceType
    source_ref: list[str] = field(default_factory=list)
    method: str | None = None
    confidence: float | None = None
    staleness_days: float | None = None
    is_stale: bool = False
    overlay: Any | None = None
    overlay_provenance: list[str] = field(default_factory=list)
    overlay_source_type: str | None = None
    overlay_source_ref: list[str] = field(default_factory=list)
    overlay_method: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_type": self.source_type,
        }
        if self.source_ref:
            payload["source_ref"] = list(self.source_ref)
        if self.method is not None:
            payload["method"] = self.method
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.staleness_days is not None:
            payload["staleness_days"] = self.staleness_days
        if self.is_stale:
            payload["is_stale"] = self.is_stale
        if self.overlay is not None:
            payload["overlay"] = self.overlay
        if self.overlay_provenance:
            payload["overlay_provenance"] = list(self.overlay_provenance)
        if self.overlay_source_type is not None:
            payload["overlay_source_type"] = self.overlay_source_type
        if self.overlay_source_ref:
            payload["overlay_source_ref"] = list(self.overlay_source_ref)
        if self.overlay_method is not None:
            payload["overlay_method"] = self.overlay_method
        if self.extras:
            payload["extras"] = self.extras
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> FieldAnnotation:
        source_type = data.get("source_type") or data.get("source") or "unknown"
        extras = data.get("extras") or {}
        overlay_provenance = data.get("overlay_provenance") or []
        source_ref_raw = data.get("source_ref") or []
        source_ref = [source_ref_raw] if isinstance(source_ref_raw, str) else [str(item) for item in source_ref_raw]
        return FieldAnnotation(
            source_type=source_type,
            source_ref=source_ref,
            method=data.get("method"),
            confidence=data.get("confidence"),
            staleness_days=data.get("staleness_days"),
            is_stale=bool(data.get("is_stale", False)),
            overlay=data.get("overlay"),
            overlay_provenance=[str(item) for item in overlay_provenance],
            overlay_source_type=data.get("overlay_source_type"),
            overlay_source_ref=[str(item) for item in (data.get("overlay_source_ref") or [])],
            overlay_method=data.get("overlay_method"),
            extras=dict(extras) if isinstance(extras, dict) else {},
        )


@dataclass
class ProfileLibrarySection:
    """Canonical profile data sourced from the cloud library."""

    profile_id: str
    profile_type: str = "line"
    tenant_id: str | None = None
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "identity": self.identity,
            "taxonomy": self.taxonomy,
            "parents": list(self.parents),
            "policies": self.policies,
            "stable_knowledge": self.stable_knowledge,
            "lifecycle": self.lifecycle,
            "traits": self.traits,
            "curated_targets": self.curated_targets,
            "diffs_vs_parent": self.diffs_vs_parent,
            "tags": list(self.tags),
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any], *, fallback_id: str) -> ProfileLibrarySection:
        parents_raw = data.get("parents") or []
        parents = [parents_raw] if isinstance(parents_raw, str) else [str(item) for item in parents_raw]
        tags_raw = data.get("tags") or []
        tags = [tags_raw] if isinstance(tags_raw, str) else [str(item) for item in tags_raw]
        return ProfileLibrarySection(
            profile_id=str(data.get("profile_id") or fallback_id),
            profile_type=str(data.get("profile_type", "line")),
            tenant_id=data.get("tenant_id"),
            identity=_as_dict(data.get("identity")),
            taxonomy=_as_dict(data.get("taxonomy")),
            parents=parents,
            policies=_as_dict(data.get("policies")),
            stable_knowledge=_as_dict(data.get("stable_knowledge")),
            lifecycle=_as_dict(data.get("lifecycle")),
            traits=_as_dict(data.get("traits")),
            curated_targets=_as_dict(data.get("curated_targets")),
            diffs_vs_parent=_as_dict(data.get("diffs_vs_parent")),
            tags=tags,
            metadata=_as_dict(data.get("metadata")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class ProfileLocalSection:
    """Locally authoritative profile details stored on the edge."""

    species: str | None = None
    general: dict[str, Any] = field(default_factory=dict)
    local_overrides: dict[str, Any] = field(default_factory=dict)
    resolver_state: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    run_history: list[RunEvent] = field(default_factory=list)
    harvest_history: list[HarvestEvent] = field(default_factory=list)
    statistics: list[YieldStatistic] = field(default_factory=list)
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "general": self.general,
            "local_overrides": self.local_overrides,
            "resolver_state": self.resolver_state,
            "citations": [asdict(cit) for cit in self.citations],
            "run_history": [event.to_json() for event in self.run_history],
            "harvest_history": [event.to_json() for event in self.harvest_history],
            "statistics": [stat.to_json() for stat in self.statistics],
        }
        if self.species is not None:
            payload["species"] = self.species
        if self.last_resolved is not None:
            payload["last_resolved"] = self.last_resolved
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileLocalSection:
        citations = [Citation(**item) for item in data.get("citations", []) or [] if isinstance(item, Mapping)]
        run_history: list[RunEvent] = []
        for item in data.get("run_history", []) or []:
            if isinstance(item, Mapping):
                run_history.append(RunEvent.from_json(item))
        harvest_history: list[HarvestEvent] = []
        for item in data.get("harvest_history", []) or []:
            if isinstance(item, Mapping):
                harvest_history.append(HarvestEvent.from_json(item))
        statistics: list[YieldStatistic] = []
        for item in data.get("statistics", []) or []:
            if isinstance(item, Mapping):
                statistics.append(YieldStatistic.from_json(item))
        return ProfileLocalSection(
            species=data.get("species"),
            general=_as_dict(data.get("general")),
            local_overrides=_as_dict(data.get("local_overrides") or data.get("overrides")),
            resolver_state=_as_dict(data.get("resolver_state")),
            citations=citations,
            run_history=run_history,
            harvest_history=harvest_history,
            statistics=statistics,
            last_resolved=data.get("last_resolved"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass
class ResolvedTarget:
    """Resolved target value including provenance annotations."""

    value: Any
    annotation: FieldAnnotation
    citations: list[Citation] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "annotation": self.annotation.to_json(),
            "citations": [asdict(cit) for cit in self.citations],
        }

    def to_legacy(self) -> dict[str, Any]:
        """Return a legacy ``variables`` style payload for compatibility."""

        payload: dict[str, Any] = {
            "value": self.value,
            "source": self.annotation.source_type,
            "annotation": self.annotation.to_json(),
        }
        if self.citations:
            payload["citations"] = [asdict(cit) for cit in self.citations]
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ResolvedTarget:
        if "annotation" in data and isinstance(data["annotation"], dict):
            annotation = FieldAnnotation.from_json(data["annotation"])
        else:
            annotation = FieldAnnotation(
                source_type=data.get("source") or data.get("source_type") or "unknown",
                source_ref=data.get("source_ref") or [],
                method=data.get("method"),
                confidence=data.get("confidence"),
            )
        citations = [Citation(**cit) for cit in data.get("citations", [])]
        return ResolvedTarget(value=data.get("value"), annotation=annotation, citations=citations)


@dataclass
class ProfileContribution:
    profile_id: str
    child_id: str
    stats_version: str | None = None
    computed_at: str | None = None
    n_runs: int | None = None
    weight: float | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "child_id": self.child_id,
        }
        if self.stats_version is not None:
            payload["stats_version"] = self.stats_version
        if self.computed_at is not None:
            payload["computed_at"] = self.computed_at
        if self.n_runs is not None:
            payload["n_runs"] = self.n_runs
        if self.weight is not None:
            payload["weight"] = self.weight
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ProfileContribution:
        return ProfileContribution(
            profile_id=str(data.get("profile_id", "")),
            child_id=str(data.get("child_id", "")),
            stats_version=data.get("stats_version"),
            computed_at=data.get("computed_at"),
            n_runs=data.get("n_runs"),
            weight=data.get("weight"),
        )


@dataclass
class ComputedStatSnapshot:
    stats_version: str | None = None
    computed_at: str | None = None
    snapshot_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    contributions: list[ProfileContribution] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "payload": self.payload,
            "contributions": [contrib.to_json() for contrib in self.contributions],
        }
        if self.stats_version is not None:
            payload["stats_version"] = self.stats_version
        if self.computed_at is not None:
            payload["computed_at"] = self.computed_at
        if self.snapshot_id is not None:
            payload["snapshot_id"] = self.snapshot_id
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ComputedStatSnapshot:
        contributions = [
            ProfileContribution.from_json(item)
            for item in data.get("contributions", []) or []
            if isinstance(item, dict)
        ]
        payload = data.get("payload") or {}
        return ComputedStatSnapshot(
            stats_version=data.get("stats_version"),
            computed_at=data.get("computed_at"),
            snapshot_id=data.get("snapshot_id"),
            payload=payload if isinstance(payload, dict) else {},
            contributions=contributions,
        )


@dataclass
class ProfileResolvedSection:
    """Runtime resolved data derived from local/cloud/manual sources."""

    thresholds: dict[str, Any] = field(default_factory=dict)
    resolved_targets: dict[str, ResolvedTarget] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    citation_map: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_resolved: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "thresholds": dict(self.thresholds),
            "resolved_targets": {key: value.to_json() for key, value in self.resolved_targets.items()},
        }
        if self.variables:
            payload["variables"] = dict(self.variables)
        if self.citation_map:
            payload["citation_map"] = dict(self.citation_map)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.last_resolved is not None:
            payload["last_resolved"] = self.last_resolved
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileResolvedSection:
        thresholds = _as_dict(data.get("thresholds"))
        resolved_targets: dict[str, ResolvedTarget] = {}
        resolved_payload = data.get("resolved_targets") or {}
        if isinstance(resolved_payload, Mapping):
            for key, value in resolved_payload.items():
                if isinstance(value, Mapping):
                    resolved_targets[str(key)] = ResolvedTarget.from_json(dict(value))
        variables = _as_dict(data.get("variables"))
        for key, target in resolved_targets.items():
            variables.setdefault(str(key), target.to_legacy())
        citation_map = _as_dict(data.get("citation_map"))
        metadata = _as_dict(data.get("metadata"))
        last_resolved = data.get("last_resolved")
        return ProfileResolvedSection(
            thresholds=thresholds,
            resolved_targets=resolved_targets,
            variables=variables,
            citation_map=citation_map,
            metadata=metadata,
            last_resolved=last_resolved,
        )


@dataclass
class ProfileComputedSection:
    """Computed statistics cached from the cloud resolver."""

    snapshots: list[ComputedStatSnapshot] = field(default_factory=list)
    latest: ComputedStatSnapshot | None = None
    contributions: list[ProfileContribution] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshots": [snapshot.to_json() for snapshot in self.snapshots],
        }
        if self.latest is not None:
            payload["latest"] = self.latest.to_json()
        if self.contributions:
            payload["contributions"] = [contrib.to_json() for contrib in self.contributions]
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileComputedSection:
        snapshots: list[ComputedStatSnapshot] = []
        snapshot_payloads = data.get("snapshots")
        if isinstance(snapshot_payloads, list):
            for item in snapshot_payloads:
                if isinstance(item, Mapping):
                    snapshots.append(ComputedStatSnapshot.from_json(dict(item)))
        latest_payload = data.get("latest")
        latest = ComputedStatSnapshot.from_json(dict(latest_payload)) if isinstance(latest_payload, Mapping) else None
        contributions_payload = data.get("contributions")
        contributions: list[ProfileContribution] = []
        if isinstance(contributions_payload, list):
            for item in contributions_payload:
                if isinstance(item, Mapping):
                    contributions.append(ProfileContribution.from_json(dict(item)))
        metadata = _as_dict(data.get("metadata"))
        if latest and all(latest is not snap for snap in snapshots):
            snapshots.insert(0, latest)
        return ProfileComputedSection(
            snapshots=snapshots,
            latest=latest or (snapshots[0] if snapshots else None),
            contributions=contributions,
            metadata=metadata,
        )


@dataclass
class ProfileLineageEntry:
    """An entry in the lineage chain used for inheritance."""

    profile_id: str
    profile_type: str = "line"
    depth: int = 0
    role: str = "self"
    tenant_id: str | None = None
    parents: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "depth": self.depth,
            "role": self.role,
            "parents": list(self.parents),
            "tags": list(self.tags),
            "identity": dict(self.identity),
            "taxonomy": dict(self.taxonomy),
            "policies": dict(self.policies),
            "stable_knowledge": dict(self.stable_knowledge),
            "lifecycle": dict(self.lifecycle),
            "traits": dict(self.traits),
            "curated_targets": dict(self.curated_targets),
            "diffs_vs_parent": dict(self.diffs_vs_parent),
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileLineageEntry:
        parents_raw = data.get("parents") or []
        parents = [parents_raw] if isinstance(parents_raw, str) else [str(item) for item in parents_raw]
        tags_raw = data.get("tags") or []
        tags = [tags_raw] if isinstance(tags_raw, str) else [str(item) for item in tags_raw]
        return ProfileLineageEntry(
            profile_id=str(data.get("profile_id")),
            profile_type=str(data.get("profile_type", "line")),
            depth=int(data.get("depth", 0)),
            role=str(data.get("role", "self")),
            tenant_id=data.get("tenant_id"),
            parents=parents,
            tags=tags,
            identity=_as_dict(data.get("identity")),
            taxonomy=_as_dict(data.get("taxonomy")),
            policies=_as_dict(data.get("policies")),
            stable_knowledge=_as_dict(data.get("stable_knowledge")),
            lifecycle=_as_dict(data.get("lifecycle")),
            traits=_as_dict(data.get("traits")),
            curated_targets=_as_dict(data.get("curated_targets")),
            diffs_vs_parent=_as_dict(data.get("diffs_vs_parent")),
            metadata=_as_dict(data.get("metadata")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class ProfileSections:
    """Grouped sections that compose the full profile envelope."""

    library: ProfileLibrarySection
    local: ProfileLocalSection
    resolved: ProfileResolvedSection
    computed: ProfileComputedSection

    def to_json(self) -> dict[str, Any]:
        return {
            "library": self.library.to_json(),
            "local": self.local.to_json(),
            "resolved": self.resolved.to_json(),
            "computed": self.computed.to_json(),
        }

    @staticmethod
    def from_json(data: Mapping[str, Any], *, fallback_id: str) -> ProfileSections:
        library_payload = data.get("library")
        if isinstance(library_payload, Mapping):
            library = ProfileLibrarySection.from_json(library_payload, fallback_id=fallback_id)
        else:
            library = ProfileLibrarySection(profile_id=fallback_id)

        local_payload = data.get("local")
        local = (
            ProfileLocalSection.from_json(local_payload)
            if isinstance(local_payload, Mapping)
            else ProfileLocalSection()
        )

        resolved_payload = data.get("resolved")
        resolved = (
            ProfileResolvedSection.from_json(resolved_payload)
            if isinstance(resolved_payload, Mapping)
            else ProfileResolvedSection()
        )

        computed_payload = data.get("computed")
        computed = (
            ProfileComputedSection.from_json(computed_payload)
            if isinstance(computed_payload, Mapping)
            else ProfileComputedSection()
        )

        return ProfileSections(
            library=library,
            local=local,
            resolved=resolved,
            computed=computed,
        )


@dataclass
class BioProfile:
    """Comprehensive offline profile representation used by the add-on."""

    profile_id: str
    display_name: str
    profile_type: str = "line"
    species: str | None = None
    tenant_id: str | None = None
    parents: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    library_metadata: dict[str, Any] = field(default_factory=dict)
    library_created_at: str | None = None
    library_updated_at: str | None = None
    local_overrides: dict[str, Any] = field(default_factory=dict)
    resolver_state: dict[str, Any] = field(default_factory=dict)
    resolved_targets: dict[str, ResolvedTarget] = field(default_factory=dict)
    computed_stats: list[ComputedStatSnapshot] = field(default_factory=list)
    general: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    local_metadata: dict[str, Any] = field(default_factory=dict)
    run_history: list[RunEvent] = field(default_factory=list)
    harvest_history: list[HarvestEvent] = field(default_factory=list)
    statistics: list[YieldStatistic] = field(default_factory=list)
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sections: ProfileSections | None = None
    lineage: list[ProfileLineageEntry] = field(default_factory=list)

    @property
    def plant_id(self) -> str:
        """Backward compatible alias for :attr:`profile_id`."""

        return self.profile_id

    @plant_id.setter
    def plant_id(self, value: str) -> None:
        self.profile_id = value

    @property
    def species_profile_id(self) -> str | None:
        """Return the associated species identifier, if any."""

        return self.species

    @species_profile_id.setter
    def species_profile_id(self, value: str | None) -> None:
        self.species = value

    def resolved_values(self) -> dict[str, Any]:
        """Return the resolved values without metadata."""

        return {key: target.value for key, target in self.resolved_targets.items()}

    def add_run_event(self, event: RunEvent) -> None:
        """Append a normalised run event to the local history."""

        normalised = RunEvent.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        self.run_history.append(normalised)

    def add_harvest_event(self, event: HarvestEvent) -> None:
        """Append a harvest event and keep identifiers consistent."""

        normalised = HarvestEvent.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        if normalised.run_id is None and self.run_history:
            normalised.run_id = self.run_history[-1].run_id
        self.harvest_history.append(normalised)

    def to_json(self) -> dict[str, Any]:
        resolved_payload = {key: value.to_json() for key, value in self.resolved_targets.items()}
        variables_payload = {key: value.to_legacy() for key, value in self.resolved_targets.items()}
        thresholds_payload = self.resolved_values()

        sections = self._ensure_sections()
        library_section = sections.library
        local_section = sections.local

        payload = {
            "profile_id": self.profile_id,
            "plant_id": self.profile_id,
            "display_name": self.display_name,
            "profile_type": self.profile_type,
            "species": self.species,
            "tenant_id": self.tenant_id,
            "parents": list(self.parents),
            "identity": self.identity,
            "taxonomy": self.taxonomy,
            "policies": self.policies,
            "stable_knowledge": self.stable_knowledge,
            "lifecycle": self.lifecycle,
            "traits": self.traits,
            "tags": list(self.tags),
            "curated_targets": self.curated_targets,
            "diffs_vs_parent": self.diffs_vs_parent,
            "local_overrides": self.local_overrides,
            "resolver_state": self.resolver_state,
            "resolved_targets": resolved_payload,
            "variables": variables_payload,
            "thresholds": thresholds_payload,
            "computed_stats": [snapshot.to_json() for snapshot in self.computed_stats],
            "general": self.general,
            "citations": [asdict(cit) for cit in self.citations],
            "run_history": [event.to_json() for event in self.run_history],
            "harvest_history": [event.to_json() for event in self.harvest_history],
            "statistics": [stat.to_json() for stat in self.statistics],
            "last_resolved": self.last_resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        if self.library_metadata:
            payload["library_metadata"] = self.library_metadata
        if self.library_created_at is not None:
            payload["library_created_at"] = self.library_created_at
        if self.library_updated_at is not None:
            payload["library_updated_at"] = self.library_updated_at
        if self.local_metadata:
            payload["local_metadata"] = self.local_metadata

        payload["library"] = library_section.to_json()
        payload["local"] = local_section.to_json()
        payload["sections"] = sections.to_json()
        if self.lineage:
            payload["lineage"] = [entry.to_json() for entry in self.lineage]

        return payload

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary of the profile."""

        sensors = self.general.get("sensors")
        sensor_summary = dict(sensors) if isinstance(sensors, dict) else {}
        return {
            "profile_id": self.profile_id,
            "plant_id": self.profile_id,
            "name": self.display_name,
            "profile_type": self.profile_type,
            "species": self.species,
            "tenant_id": self.tenant_id,
            "parents": list(self.parents),
            "sensors": sensor_summary,
            "targets": self.resolved_values(),
            "tags": list(self.tags),
            "last_resolved": self.last_resolved,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> BioProfile:
        """Create a BioProfile from a dictionary."""

        fallback_id = data.get("profile_id") or data.get("plant_id") or data.get("name") or "profile"
        profile_id = str(fallback_id)

        sections_payload = data.get("sections")
        sections = (
            ProfileSections.from_json(sections_payload, fallback_id=profile_id)
            if isinstance(sections_payload, Mapping)
            else None
        )

        if sections is not None:
            library_section = sections.library
            local_section = sections.local
            resolved_section = sections.resolved
            computed_section = sections.computed
        else:
            library_payload = data.get("library")
            library_section = (
                ProfileLibrarySection.from_json(library_payload, fallback_id=profile_id)
                if isinstance(library_payload, Mapping)
                else None
            )
            local_payload = data.get("local")
            local_section = ProfileLocalSection.from_json(local_payload) if isinstance(local_payload, Mapping) else None
            resolved_section = None
            computed_section = None

        if library_section:
            profile_type = str(library_section.profile_type or "line")
        else:
            profile_type = str(data.get("profile_type") or "line")

        resolved_targets: dict[str, ResolvedTarget] = {}
        if resolved_section is not None:
            resolved_source = resolved_section.resolved_targets
        else:
            resolved_source = (
                data.get("resolved_targets") if isinstance(data.get("resolved_targets"), Mapping) else None
            )
        if resolved_source:
            for key, value in resolved_source.items():
                if isinstance(value, ResolvedTarget):
                    resolved_targets[str(key)] = value
                elif isinstance(value, Mapping):
                    resolved_targets[str(key)] = ResolvedTarget.from_json(dict(value))

        if resolved_section is not None:
            legacy_variables = resolved_section.variables
        elif isinstance(data.get("variables"), Mapping):
            legacy_variables = data.get("variables")
        else:
            legacy_variables = None
        if isinstance(legacy_variables, Mapping):
            for key, value in legacy_variables.items():
                key_str = str(key)
                if key_str in resolved_targets or not isinstance(value, Mapping):
                    continue
                annotation = FieldAnnotation(source_type=value.get("source") or "unknown")
                citations = [Citation(**cit) for cit in value.get("citations", []) if isinstance(cit, Mapping)]
                resolved_targets[key_str] = ResolvedTarget(
                    value=value.get("value"),
                    annotation=annotation,
                    citations=citations,
                )

        if resolved_section is not None:
            legacy_thresholds = resolved_section.thresholds
        elif isinstance(data.get("thresholds"), Mapping):
            legacy_thresholds = data.get("thresholds")
        else:
            legacy_thresholds = None
        if isinstance(legacy_thresholds, Mapping):
            for key, value in legacy_thresholds.items():
                key_str = str(key)
                if key_str in resolved_targets:
                    continue
                annotation = FieldAnnotation(source_type="unknown")
                resolved_targets[key_str] = ResolvedTarget(value=value, annotation=annotation, citations=[])

        top_level_citations = [Citation(**cit) for cit in data.get("citations", []) if isinstance(cit, dict)]
        citations = list(local_section.citations) if local_section and local_section.citations else top_level_citations

        if computed_section is not None:
            computed_stats = list(computed_section.snapshots)
        else:
            computed_stats = [
                ComputedStatSnapshot.from_json(item)
                for item in data.get("computed_stats", []) or []
                if isinstance(item, dict)
            ]

        if library_section:
            parents = list(library_section.parents)
            tags = list(library_section.tags)
            identity = library_section.identity
            taxonomy = library_section.taxonomy
            policies = library_section.policies
            stable_knowledge = library_section.stable_knowledge
            lifecycle = library_section.lifecycle
            traits = library_section.traits
            curated_targets = library_section.curated_targets
            diffs_vs_parent = library_section.diffs_vs_parent
            tenant_id = library_section.tenant_id
            library_metadata = library_section.metadata
            library_created_at = library_section.created_at
            library_updated_at = library_section.updated_at
        else:
            parents_raw = data.get("parents") or []
            parents = [parents_raw] if isinstance(parents_raw, str) else [str(parent) for parent in parents_raw]
            tags_raw = data.get("tags") or []
            tags = [tags_raw] if isinstance(tags_raw, str) else [str(tag) for tag in tags_raw]
            identity = _as_dict(data.get("identity"))
            taxonomy = _as_dict(data.get("taxonomy"))
            policies = _as_dict(data.get("policies"))
            stable_knowledge = _as_dict(data.get("stable_knowledge"))
            lifecycle = _as_dict(data.get("lifecycle"))
            traits = _as_dict(data.get("traits"))
            curated_targets = _as_dict(data.get("curated_targets"))
            diffs_vs_parent = _as_dict(data.get("diffs_vs_parent"))
            tenant_id = data.get("tenant_id")
            library_metadata = _as_dict(data.get("library_metadata"))
            library_created_at = data.get("library_created_at")
            library_updated_at = data.get("library_updated_at")

        if local_section:
            species = local_section.species
            general = local_section.general
            local_overrides = local_section.local_overrides
            resolver_state = local_section.resolver_state
            last_resolved = local_section.last_resolved
            created_at = local_section.created_at
            updated_at = local_section.updated_at
            local_metadata = dict(local_section.metadata)
            run_history = list(local_section.run_history)
            harvest_history = list(local_section.harvest_history)
            statistics = list(local_section.statistics)
        else:
            species = data.get("species")
            general = _as_dict(data.get("general"))
            local_overrides = _as_dict(data.get("local_overrides") or data.get("overrides"))
            resolver_state = _as_dict(data.get("resolver_state"))
            last_resolved = data.get("last_resolved")
            created_at = data.get("created_at")
            updated_at = data.get("updated_at")
            local_metadata = _as_dict(data.get("local_metadata"))
            run_history = [
                RunEvent.from_json(item)
                for item in data.get("run_history", []) or []
                if isinstance(item, Mapping)
            ]
            harvest_history = [
                HarvestEvent.from_json(item)
                for item in data.get("harvest_history", []) or []
                if isinstance(item, Mapping)
            ]
            statistics = [
                YieldStatistic.from_json(item)
                for item in data.get("statistics", []) or []
                if isinstance(item, Mapping)
            ]

        if resolved_section is not None:
            if resolved_section.metadata:
                local_metadata.update(resolved_section.metadata)
            if resolved_section.last_resolved and not last_resolved:
                last_resolved = resolved_section.last_resolved
            citation_map = resolved_section.citation_map
            if citation_map:
                local_metadata.setdefault("citation_map", dict(citation_map))

        extra_kwargs: dict[str, Any] = {}
        if profile_type == "species":
            profile_cls: type[BioProfile] = SpeciesProfile
            cultivar_ids_raw = data.get("cultivar_ids")
            if not isinstance(cultivar_ids_raw, list):
                cultivar_ids_raw = local_metadata.get("cultivar_ids") if isinstance(local_metadata, Mapping) else []
            cultivar_ids: list[str] = []
            if isinstance(cultivar_ids_raw, list):
                for item in cultivar_ids_raw:
                    cultivar_ids.append(str(item))
            extra_kwargs["cultivar_ids"] = cultivar_ids
        elif profile_type in {"cultivar", "line"}:
            profile_cls = CultivarProfile
            area = data.get("area_m2")
            if area is None:
                meta_area = local_metadata.get("area_m2") if isinstance(local_metadata, Mapping) else None
                area = meta_area
            try:
                extra_kwargs["area_m2"] = float(area) if area is not None else None
            except (TypeError, ValueError):
                extra_kwargs["area_m2"] = None
        else:
            profile_cls = BioProfile

        profile = profile_cls(
            profile_id=profile_id,
            display_name=data.get("display_name") or data.get("name") or profile_id,
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
            citations=citations,
            local_metadata=local_metadata,
            run_history=run_history,
            harvest_history=harvest_history,
            statistics=statistics,
            last_resolved=last_resolved,
            created_at=created_at,
            updated_at=updated_at,
            sections=sections,
            lineage=[
                ProfileLineageEntry.from_json(item) for item in data.get("lineage", []) if isinstance(item, Mapping)
            ],
            **extra_kwargs,
        )

        return profile

    # ------------------------------------------------------------------
    def library_section(self) -> ProfileLibrarySection:
        return ProfileLibrarySection(
            profile_id=self.profile_id,
            profile_type=self.profile_type,
            tenant_id=self.tenant_id,
            identity=dict(self.identity),
            taxonomy=dict(self.taxonomy),
            parents=list(self.parents),
            policies=dict(self.policies),
            stable_knowledge=dict(self.stable_knowledge),
            lifecycle=dict(self.lifecycle),
            traits=dict(self.traits),
            curated_targets=dict(self.curated_targets),
            diffs_vs_parent=dict(self.diffs_vs_parent),
            tags=list(self.tags),
            metadata=dict(self.library_metadata),
            created_at=self.library_created_at,
            updated_at=self.library_updated_at,
        )

    def local_section(self) -> ProfileLocalSection:
        return ProfileLocalSection(
            species=self.species,
            general=dict(self.general),
            local_overrides=dict(self.local_overrides),
            resolver_state=dict(self.resolver_state),
            citations=[Citation(**asdict(cit)) for cit in self.citations],
            run_history=[RunEvent.from_json(event.to_json()) for event in self.run_history],
            harvest_history=[HarvestEvent.from_json(event.to_json()) for event in self.harvest_history],
            statistics=[YieldStatistic.from_json(stat.to_json()) for stat in self.statistics],
            last_resolved=self.last_resolved,
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=dict(self.local_metadata),
        )

    def resolved_section(self) -> ProfileResolvedSection:
        resolved_targets = dict(self.resolved_targets)
        thresholds = self.resolved_values()
        variables = {key: target.to_legacy() for key, target in resolved_targets.items()}
        metadata = dict(self.local_metadata)
        citation_map = {}
        raw_citation_map = metadata.get("citation_map") if isinstance(metadata.get("citation_map"), Mapping) else None
        if isinstance(raw_citation_map, Mapping):
            citation_map = dict(raw_citation_map)
        return ProfileResolvedSection(
            thresholds=thresholds,
            resolved_targets=resolved_targets,
            variables=variables,
            citation_map=citation_map,
            metadata=metadata,
            last_resolved=self.last_resolved,
        )

    def computed_section(self) -> ProfileComputedSection:
        snapshots = list(self.computed_stats)
        latest = snapshots[0] if snapshots else None
        contributions: list[ProfileContribution] = []
        if latest:
            contributions = list(latest.contributions)
        return ProfileComputedSection(
            snapshots=snapshots,
            latest=latest,
            contributions=contributions,
            metadata={},
        )

    def refresh_sections(self) -> ProfileSections:
        """Refresh cached :class:`ProfileSections` to match current fields."""

        library = self.library_section()
        local = self.local_section()
        resolved = self.resolved_section()
        computed = self.computed_section()

        if self.sections is None:
            self.sections = ProfileSections(
                library=library,
                local=local,
                resolved=resolved,
                computed=computed,
            )
            return self.sections

        existing = self.sections

        merged_resolved_metadata = dict(existing.resolved.metadata)
        merged_resolved_metadata.update(resolved.metadata)
        resolved.metadata = merged_resolved_metadata

        merged_citation_map = dict(existing.resolved.citation_map)
        if resolved.citation_map:
            merged_citation_map.update(resolved.citation_map)
        resolved.citation_map = merged_citation_map

        merged_computed_metadata = dict(existing.computed.metadata)
        merged_computed_metadata.update(computed.metadata)
        computed.metadata = merged_computed_metadata

        if computed.latest is None and existing.computed.latest is not None:
            computed.latest = existing.computed.latest
        if not computed.snapshots and existing.computed.snapshots:
            computed.snapshots = list(existing.computed.snapshots)
        if not computed.contributions and existing.computed.contributions:
            computed.contributions = list(existing.computed.contributions)

        existing.library = library
        existing.local = local
        existing.resolved = resolved
        existing.computed = computed
        self.sections = existing
        return self.sections

    def _ensure_sections(self) -> ProfileSections:
        return self.refresh_sections()


@dataclass
class SpeciesProfile(BioProfile):
    """Represents a species-level BioProfile that can be inherited from."""

    profile_type: str = "species"
    cultivar_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.species:
            self.species = self.profile_id

    def to_json(self) -> dict[str, Any]:
        payload = super().to_json()
        payload["profile_type"] = "species"
        if self.cultivar_ids:
            payload["cultivar_ids"] = list({str(cid) for cid in self.cultivar_ids})
        return payload


@dataclass
class CultivarProfile(BioProfile):
    """Represents a cultivar profile inheriting from a species entry."""

    profile_type: str = "cultivar"
    area_m2: float | None = None

    def to_json(self) -> dict[str, Any]:
        payload = super().to_json()
        payload["profile_type"] = "cultivar"
        if self.area_m2 is not None:
            payload["area_m2"] = self.area_m2
        return payload
