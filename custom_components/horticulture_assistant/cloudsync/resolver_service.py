from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .edge_store import EdgeSyncStore

UTC = getattr(datetime, "UTC", timezone.utc)


@dataclass(slots=True)
class ResolveResult:
    value: Any
    provenance: list[str]
    overlay: Any | None
    overlay_provenance: list[str]
    staleness_days: float | None


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

        for entry in lineage:
            local_value = self._extract(entry.local_overrides, field_path)
            if local_value is not None:
                value = local_value
                provenance.append(f"local:{entry.profile_id}")
                found = True
                break
            curated = self._extract(entry.cloud_payload.get("curated_targets", {}), field_path)
            if curated is not None:
                value = curated
                provenance.append(f"curated:{entry.profile_id}")
                found = True
                break
            diffs = self._extract(entry.cloud_payload.get("diffs_vs_parent", {}), field_path)
            if diffs is not None:
                value = diffs
                provenance.append(f"override:{entry.profile_id}")
                found = True
                break

        if not found:
            fallback = self.fallback_provider(field_path)
            if fallback is not None:
                value = fallback
                provenance.append("fallback:system")
            else:
                provenance.append("default:none")

        overlay, overlay_meta = self._resolve_overlay(lineage, field_path, now)
        staleness_days = overlay_meta.get("staleness_days")

        return ResolveResult(
            value=value,
            provenance=provenance,
            overlay=overlay,
            overlay_provenance=overlay_meta.get("provenance", []),
            staleness_days=staleness_days,
        )

    def resolve_many(self, profile_id: str, fields: Iterable[str], *, now: datetime | None = None) -> dict[str, ResolveResult]:
        results: dict[str, ResolveResult] = {}
        for field in fields:
            results[field] = self.resolve_field(profile_id, field, now=now)
        return results

    # ------------------------------------------------------------------
    def _load_lineage(self, profile_id: str) -> list["LineageEntry"]:
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

    def _resolve_overlay(
        self,
        lineage: list["LineageEntry"],
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
        if computed_at_raw:
            computed_at = datetime.fromisoformat(str(computed_at_raw).replace("Z", "+00:00"))
            staleness = now - computed_at
            staleness_days = staleness.total_seconds() / 86400
            if staleness > self.stats_ttl:
                return None, {"provenance": ["computed:stale"], "staleness_days": staleness_days}
        overlay = self._extract(stats_payload.get("payload", {}), field_path)
        provenance = [f"computed:{species_id}"] if overlay is not None else []
        return overlay, {"provenance": provenance, "staleness_days": staleness_days}

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


@dataclass(slots=True)
class LineageEntry:
    profile_id: str
    depth: int
    cloud_payload: dict[str, Any]
    local_overrides: dict[str, Any]

