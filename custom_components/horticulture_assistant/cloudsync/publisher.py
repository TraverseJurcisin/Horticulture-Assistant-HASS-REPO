"""Helper that converts profile mutations into sync events."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .events import SyncEvent

try:
    UTC = datetime.UTC  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..profile.schema import (
        BioProfile,
        ComputedStatSnapshot,
        CultivationEvent,
        HarvestEvent,
        NutrientApplication,
        RunEvent,
    )
    from .manager import CloudSyncManager


def _normalise_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    result: MutableMapping[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            result[str(key)] = _normalise_mapping(value)
        elif isinstance(value, list):
            result[str(key)] = list(value)
        else:
            result[str(key)] = value
    return dict(result)


def _metadata(**fields: Any) -> dict[str, Any]:
    return {key: value for key, value in fields.items() if value not in (None, "", [], {})}


@dataclass(slots=True)
class CloudSyncPublisher:
    """Publish edge mutations into the cloud sync outbox."""

    manager: CloudSyncManager
    device_id: str

    @property
    def ready(self) -> bool:
        return bool(self.manager.config.ready)

    def publish(
        self,
        entity_type: str,
        entity_id: str,
        *,
        op: str = "upsert",
        patch: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SyncEvent | None:
        if not self.ready:
            return None

        tenant_id = self.manager.config.tenant_id or "local"
        org_id = self.manager.config.organization_id
        vector = self.manager.store.next_vector(entity_type, entity_id, self.device_id)
        event = SyncEvent(
            event_id=uuid4().hex,
            tenant_id=tenant_id,
            device_id=self.device_id,
            ts=datetime.now(tz=UTC),
            entity_type=entity_type,
            entity_id=str(entity_id),
            op=op,
            patch=_normalise_mapping(patch) if patch else None,
            vector=vector,
            org_id=str(org_id) if org_id else None,
            metadata=_normalise_mapping(metadata) if metadata else {},
        )
        self.manager.store.append_outbox(event)
        return event

    # ------------------------------------------------------------------
    def publish_profile(self, profile: BioProfile, *, initial: bool = False) -> SyncEvent | None:
        patch = profile.to_json()
        metadata = _metadata(
            profile_id=profile.profile_id,
            profile_type=profile.profile_type,
            species_id=profile.species,
            initial_sync=initial,
        )
        return self.publish("profile", profile.profile_id, patch=patch, metadata=metadata)

    def publish_profile_deleted(self, profile_id: str) -> SyncEvent | None:
        return self.publish("profile", profile_id, op="delete")

    def publish_run(self, event: RunEvent, *, initial: bool = False) -> SyncEvent | None:
        patch = event.to_json()
        metadata = _metadata(
            profile_id=event.profile_id,
            species_id=event.species_id,
            event_category="run",
            initial_sync=initial,
            started_at=event.started_at,
        )
        return self.publish("run_event", event.run_id, patch=patch, metadata=metadata)

    def publish_harvest(self, event: HarvestEvent, *, initial: bool = False) -> SyncEvent | None:
        patch = event.to_json()
        metadata = _metadata(
            profile_id=event.profile_id,
            species_id=event.species_id,
            event_category="harvest",
            initial_sync=initial,
            harvested_at=event.harvested_at,
        )
        return self.publish("harvest_event", event.harvest_id, patch=patch, metadata=metadata)

    def publish_nutrient(self, event: NutrientApplication, *, initial: bool = False) -> SyncEvent | None:
        patch = event.to_json()
        metadata = _metadata(
            profile_id=event.profile_id,
            species_id=event.species_id,
            event_category="nutrient",
            initial_sync=initial,
            applied_at=event.applied_at,
            product_id=event.product_id,
        )
        return self.publish("nutrient_event", event.event_id, patch=patch, metadata=metadata)

    def publish_cultivation(self, event: CultivationEvent, *, initial: bool = False) -> SyncEvent | None:
        patch = event.to_json()
        metadata = _metadata(
            profile_id=event.profile_id,
            species_id=event.species_id,
            event_category="cultivation",
            initial_sync=initial,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
        )
        return self.publish("cultivation_event", event.event_id, patch=patch, metadata=metadata)

    def publish_stat_snapshot(
        self,
        profile: BioProfile,
        snapshot: ComputedStatSnapshot,
        *,
        initial: bool = False,
    ) -> SyncEvent | None:
        version = snapshot.stats_version or "unknown"
        stat_id = snapshot.snapshot_id or f"{profile.profile_id}:{version}"
        snapshot_json = snapshot.to_json()
        scope = None
        if isinstance(snapshot.payload, Mapping):
            scope = snapshot.payload.get("scope")

        patch: dict[str, Any] = {
            "profile_id": profile.profile_id,
            "profile_type": profile.profile_type,
            "species_id": profile.species or profile.profile_id,
            "snapshots": {stat_id: snapshot_json},
            "versions": {version: snapshot_json},
            "latest_versions": {version: stat_id},
        }
        if snapshot.computed_at:
            patch["computed_at"] = snapshot.computed_at
            patch.setdefault("updated_at", snapshot.computed_at)

        metadata = _metadata(
            profile_id=profile.profile_id,
            species_id=profile.species or profile.profile_id,
            stats_version=snapshot.stats_version,
            scope=scope,
            initial_sync=initial,
        )
        return self.publish("computed", profile.profile_id, patch=patch, metadata=metadata)


__all__ = ["CloudSyncPublisher"]
