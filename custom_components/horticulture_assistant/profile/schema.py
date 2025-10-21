from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SourceType = str  # manual|clone|openplantbook|ai|curated|computed


@dataclass
class Citation:
    source: SourceType
    title: str
    url: str | None = None
    details: dict[str, Any] | None = None
    accessed: str | None = None


@dataclass
class FieldAnnotation:
    """Metadata describing how a resolved target value was obtained."""

    source_type: SourceType
    source_ref: list[str] = field(default_factory=list)
    method: str | None = None
    confidence: float | None = None
    staleness_days: float | None = None
    overlay: Any | None = None
    overlay_provenance: list[str] = field(default_factory=list)
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
        if self.overlay is not None:
            payload["overlay"] = self.overlay
        if self.overlay_provenance:
            payload["overlay_provenance"] = list(self.overlay_provenance)
        if self.extras:
            payload["extras"] = self.extras
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> "FieldAnnotation":
        source_type = data.get("source_type") or data.get("source") or "unknown"
        extras = data.get("extras") or {}
        overlay_provenance = data.get("overlay_provenance") or []
        source_ref_raw = data.get("source_ref") or []
        if isinstance(source_ref_raw, str):
            source_ref = [source_ref_raw]
        else:
            source_ref = [str(item) for item in source_ref_raw]
        return FieldAnnotation(
            source_type=source_type,
            source_ref=source_ref,
            method=data.get("method"),
            confidence=data.get("confidence"),
            staleness_days=data.get("staleness_days"),
            overlay=data.get("overlay"),
            overlay_provenance=[str(item) for item in overlay_provenance],
            extras=dict(extras) if isinstance(extras, dict) else {},
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

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ResolvedTarget":
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
    def from_json(data: dict[str, Any]) -> "ProfileContribution":
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
    def from_json(data: dict[str, Any]) -> "ComputedStatSnapshot":
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
class PlantProfile:
    """Comprehensive offline profile representation used by the add-on."""

    plant_id: str
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
    local_overrides: dict[str, Any] = field(default_factory=dict)
    resolver_state: dict[str, Any] = field(default_factory=dict)
    resolved_targets: dict[str, ResolvedTarget] = field(default_factory=dict)
    computed_stats: list[ComputedStatSnapshot] = field(default_factory=list)
    general: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def resolved_values(self) -> dict[str, Any]:
        """Return the resolved values without metadata."""

        return {key: target.value for key, target in self.resolved_targets.items()}

    def to_json(self) -> dict[str, Any]:
        return {
            "plant_id": self.plant_id,
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
            "resolved_targets": {
                key: value.to_json() for key, value in self.resolved_targets.items()
            },
            "computed_stats": [snapshot.to_json() for snapshot in self.computed_stats],
            "general": self.general,
            "citations": [asdict(cit) for cit in self.citations],
            "last_resolved": self.last_resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary of the profile."""

        sensors = self.general.get("sensors")
        if isinstance(sensors, dict):
            sensor_summary = dict(sensors)
        else:
            sensor_summary = {}
        return {
            "plant_id": self.plant_id,
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
    def from_json(data: dict[str, Any]) -> "PlantProfile":
        """Create a PlantProfile from a dictionary."""

        resolved_targets: dict[str, ResolvedTarget] = {}
        for key, value in (data.get("resolved_targets") or {}).items():
            if isinstance(value, dict):
                resolved_targets[str(key)] = ResolvedTarget.from_json(value)

        # Backwards compatibility for older ``variables`` representation
        legacy_variables = data.get("variables") or {}
        for key, value in legacy_variables.items():
            if str(key) in resolved_targets:
                continue
            if not isinstance(value, dict):
                continue
            annotation = FieldAnnotation(
                source_type=value.get("source") or "unknown",
            )
            citations = [Citation(**cit) for cit in value.get("citations", []) if isinstance(cit, dict)]
            resolved_targets[str(key)] = ResolvedTarget(value=value.get("value"), annotation=annotation, citations=citations)

        citations = [Citation(**cit) for cit in data.get("citations", []) if isinstance(cit, dict)]
        computed_stats = [
            ComputedStatSnapshot.from_json(item)
            for item in data.get("computed_stats", []) or []
            if isinstance(item, dict)
        ]

        parents_raw = data.get("parents") or []
        if isinstance(parents_raw, str):
            parents = [parents_raw]
        else:
            parents = [str(parent) for parent in parents_raw]

        tags_raw = data.get("tags") or []
        if isinstance(tags_raw, str):
            tags = [tags_raw]
        else:
            tags = [str(tag) for tag in tags_raw]

        identity = data.get("identity") or {}
        taxonomy = data.get("taxonomy") or {}
        policies = data.get("policies") or {}
        stable_knowledge = data.get("stable_knowledge") or {}
        lifecycle = data.get("lifecycle") or {}
        traits = data.get("traits") or {}
        local_overrides = data.get("local_overrides") or data.get("overrides") or {}
        resolver_state = data.get("resolver_state") or {}
        general = data.get("general") or {}

        return PlantProfile(
            plant_id=str(data.get("plant_id")),
            display_name=data.get("display_name") or data.get("name") or str(data.get("plant_id")),
            profile_type=data.get("profile_type") or "line",
            species=data.get("species"),
            tenant_id=data.get("tenant_id"),
            parents=parents,
            identity=identity if isinstance(identity, dict) else {},
            taxonomy=taxonomy if isinstance(taxonomy, dict) else {},
            policies=policies if isinstance(policies, dict) else {},
            stable_knowledge=stable_knowledge if isinstance(stable_knowledge, dict) else {},
            lifecycle=lifecycle if isinstance(lifecycle, dict) else {},
            traits=traits if isinstance(traits, dict) else {},
            tags=tags,
            curated_targets=data.get("curated_targets") or {},
            diffs_vs_parent=data.get("diffs_vs_parent") or {},
            local_overrides=local_overrides if isinstance(local_overrides, dict) else {},
            resolver_state=resolver_state if isinstance(resolver_state, dict) else {},
            resolved_targets=resolved_targets,
            computed_stats=computed_stats,
            general=general if isinstance(general, dict) else {},
            citations=citations,
            last_resolved=data.get("last_resolved"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
