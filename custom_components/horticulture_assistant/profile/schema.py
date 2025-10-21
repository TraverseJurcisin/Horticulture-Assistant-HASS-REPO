from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any


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
        return ProfileLocalSection(
            species=data.get("species"),
            general=_as_dict(data.get("general")),
            local_overrides=_as_dict(data.get("local_overrides") or data.get("overrides")),
            resolver_state=_as_dict(data.get("resolver_state")),
            citations=citations,
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
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def resolved_values(self) -> dict[str, Any]:
        """Return the resolved values without metadata."""

        return {key: target.value for key, target in self.resolved_targets.items()}

    def to_json(self) -> dict[str, Any]:
        resolved_payload = {key: value.to_json() for key, value in self.resolved_targets.items()}
        variables_payload = {key: value.to_legacy() for key, value in self.resolved_targets.items()}
        thresholds_payload = self.resolved_values()

        library_section = self.library_section()
        local_section = self.local_section()

        payload = {
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
            "resolved_targets": resolved_payload,
            "variables": variables_payload,
            "thresholds": thresholds_payload,
            "computed_stats": [snapshot.to_json() for snapshot in self.computed_stats],
            "general": self.general,
            "citations": [asdict(cit) for cit in self.citations],
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

        return payload

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary of the profile."""

        sensors = self.general.get("sensors")
        sensor_summary = dict(sensors) if isinstance(sensors, dict) else {}
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
    def from_json(data: dict[str, Any]) -> PlantProfile:
        """Create a PlantProfile from a dictionary."""

        plant_id = str(data.get("plant_id"))
        library_section: ProfileLibrarySection | None = None
        library_payload = data.get("library")
        if isinstance(library_payload, Mapping):
            library_section = ProfileLibrarySection.from_json(
                library_payload,
                fallback_id=plant_id,
            )

        local_section: ProfileLocalSection | None = None
        local_payload = data.get("local")
        if isinstance(local_payload, Mapping):
            local_section = ProfileLocalSection.from_json(local_payload)

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
            resolved_targets[str(key)] = ResolvedTarget(
                value=value.get("value"), annotation=annotation, citations=citations
            )

        legacy_thresholds = data.get("thresholds") or {}
        if isinstance(legacy_thresholds, dict):
            for key, value in legacy_thresholds.items():
                key_str = str(key)
                if key_str in resolved_targets:
                    continue
                annotation = FieldAnnotation(source_type="unknown")
                resolved_targets[key_str] = ResolvedTarget(value=value, annotation=annotation, citations=[])

        top_level_citations = [Citation(**cit) for cit in data.get("citations", []) if isinstance(cit, dict)]
        citations = local_section.citations if local_section and local_section.citations else top_level_citations
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
            local_metadata = local_section.metadata
        else:
            species = data.get("species")
            general = _as_dict(data.get("general"))
            local_overrides = _as_dict(data.get("local_overrides") or data.get("overrides"))
            resolver_state = _as_dict(data.get("resolver_state"))
            last_resolved = data.get("last_resolved")
            created_at = data.get("created_at")
            updated_at = data.get("updated_at")
            local_metadata = _as_dict(data.get("local_metadata"))

        return PlantProfile(
            plant_id=plant_id,
            display_name=data.get("display_name") or data.get("name") or plant_id,
            profile_type=(library_section.profile_type if library_section else data.get("profile_type") or "line"),
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
            last_resolved=last_resolved,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ------------------------------------------------------------------
    def library_section(self) -> ProfileLibrarySection:
        return ProfileLibrarySection(
            profile_id=self.plant_id,
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
            last_resolved=self.last_resolved,
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=dict(self.local_metadata),
        )
