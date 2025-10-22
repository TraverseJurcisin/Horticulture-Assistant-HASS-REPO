from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from .schema import (
    BioProfile,
    ComputedStatSnapshot,
    HarvestEvent,
    ProfileContribution,
    YieldStatistic,
)

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017
YIELD_STATS_VERSION = "yield/v1"


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _aggregate_harvests(harvests: Iterable[HarvestEvent]) -> tuple[float, float, int, list[float]]:
    total_yield = 0.0
    total_area = 0.0
    count = 0
    densities: list[float] = []
    for event in harvests:
        total_yield += float(event.yield_grams or 0.0)
        if event.area_m2:
            total_area += float(event.area_m2)
            density = event.yield_density()
            if density is not None:
                densities.append(density)
        count += 1
    return total_yield, total_area, count, densities


def _build_stat(
    scope: str,
    profile_id: str,
    *,
    total_yield: float,
    total_area: float,
    count: int,
    densities: list[float],
    computed_at: str | None = None,
) -> YieldStatistic:
    metrics: dict[str, float] = {}
    if count:
        metrics["harvest_count"] = float(count)
        metrics["average_yield_grams"] = round(total_yield / count, 3)
    metrics["total_yield_grams"] = round(total_yield, 3)
    if total_area:
        metrics["total_area_m2"] = round(total_area, 3)
        metrics["average_yield_density_g_m2"] = round(total_yield / total_area, 3)
    if densities:
        metrics["mean_density_g_m2"] = round(mean(densities), 3)
    computed_at_value = computed_at or _now_iso()
    return YieldStatistic(
        stat_id=f"{profile_id}:{scope}:yield",
        scope=scope,
        profile_id=profile_id,
        computed_at=computed_at_value,
        metrics=metrics,
        metadata={"source": "local_harvest_aggregation"},
    )


def _replace_snapshot(
    profile: BioProfile,
    version: str,
    snapshot: ComputedStatSnapshot | None,
) -> None:
    """Replace or append a computed snapshot while preserving other entries."""

    updated: list[ComputedStatSnapshot] = []
    replaced = False
    for existing in profile.computed_stats:
        if existing.stats_version == version:
            if snapshot is not None and not replaced:
                updated.append(snapshot)
                replaced = True
            continue
        updated.append(existing)
    if snapshot is not None and not replaced:
        updated.append(snapshot)
    profile.computed_stats = updated


def recompute_statistics(profiles: Iterable[BioProfile]) -> None:
    """Rebuild species and cultivar yield statistics in-place."""

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    species_to_harvests: defaultdict[str, list[HarvestEvent]] = defaultdict(list)
    species_breakdown: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for profile in profiles:
        harvests = list(profile.harvest_history)
        run_ids = {event.run_id for event in harvests if event.run_id}
        if not run_ids:
            run_ids = {event.run_id for event in profile.run_history if event.run_id}
        run_count = len(run_ids)

        aggregate: dict[str, Any] | None = None
        if harvests:
            total_yield, total_area, count, densities = _aggregate_harvests(harvests)
            scope = "species" if profile.profile_type == "species" else "cultivar"
            computed_at = _now_iso()
            stat = _build_stat(
                scope,
                profile.profile_id,
                total_yield=total_yield,
                total_area=total_area,
                count=count,
                densities=densities,
                computed_at=computed_at,
            )
            profile.statistics = [stat]
            metrics = dict(stat.metrics)
            snapshot_payload = {
                "scope": scope,
                "metrics": metrics,
                "harvest_count": count,
                "yields": {
                    "total_grams": round(total_yield, 3),
                    "total_area_m2": round(total_area, 3),
                },
                "densities": {
                    "average_g_m2": metrics.get("average_yield_density_g_m2"),
                    "mean_g_m2": metrics.get("mean_density_g_m2"),
                },
                "runs_tracked": run_count,
            }
            snapshot = ComputedStatSnapshot(
                stats_version=YIELD_STATS_VERSION,
                computed_at=computed_at,
                snapshot_id=f"{profile.profile_id}:{YIELD_STATS_VERSION}",
                payload=snapshot_payload,
                contributions=[],
            )
            _replace_snapshot(profile, YIELD_STATS_VERSION, snapshot)
            aggregate = {
                "child_id": profile.profile_id,
                "total_yield": total_yield,
                "total_area": total_area,
                "harvest_count": count,
                "mean_density": metrics.get("mean_density_g_m2"),
                "run_count": run_count,
            }
        else:
            profile.statistics = []
            _replace_snapshot(profile, YIELD_STATS_VERSION, None)

        species_id = profile.species_profile_id or (profile.profile_id if profile.profile_type == "species" else None)
        if species_id:
            species_to_harvests[species_id].extend(harvests)
            if aggregate is not None:
                species_breakdown[species_id].append(aggregate)

    for species_id, harvests in species_to_harvests.items():
        if not harvests:
            continue
        total_yield, total_area, count, densities = _aggregate_harvests(harvests)
        computed_at = _now_iso()
        stat = _build_stat(
            "species",
            species_id,
            total_yield=total_yield,
            total_area=total_area,
            count=count,
            densities=densities,
            computed_at=computed_at,
        )
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        existing = [s for s in target.statistics if s.scope != "species"]
        target.statistics = existing + [stat]

        contributors: list[ProfileContribution] = []
        contributor_payload: list[dict[str, Any]] = []
        for item in species_breakdown.get(species_id, []):
            weight = (item["total_yield"] / total_yield) if total_yield else None
            contributors.append(
                ProfileContribution(
                    profile_id=species_id,
                    child_id=item["child_id"],
                    stats_version=YIELD_STATS_VERSION,
                    computed_at=computed_at,
                    n_runs=item["run_count"] or None,
                    weight=round(weight, 6) if weight is not None else None,
                )
            )
            contributor_payload.append(
                {
                    "profile_id": item["child_id"],
                    "harvest_count": item["harvest_count"],
                    "total_yield_grams": round(item["total_yield"], 3),
                    "total_area_m2": round(item["total_area"], 3),
                    "mean_density_g_m2": item["mean_density"],
                    "runs_tracked": item["run_count"],
                }
            )

        species_run_ids = {event.run_id for event in harvests if event.run_id}
        metrics = dict(stat.metrics)
        snapshot_payload = {
            "scope": "species",
            "metrics": metrics,
            "harvest_count": count,
            "yields": {
                "total_grams": round(total_yield, 3),
                "total_area_m2": round(total_area, 3),
            },
            "densities": {
                "average_g_m2": metrics.get("average_yield_density_g_m2"),
                "mean_g_m2": metrics.get("mean_density_g_m2"),
            },
            "contributors": contributor_payload,
            "runs_tracked": len(species_run_ids),
        }
        snapshot = ComputedStatSnapshot(
            stats_version=YIELD_STATS_VERSION,
            computed_at=computed_at,
            snapshot_id=f"{species_id}:{YIELD_STATS_VERSION}",
            payload=snapshot_payload,
            contributions=contributors,
        )
        _replace_snapshot(target, YIELD_STATS_VERSION, snapshot)

    for profile in profiles:
        profile.refresh_sections()


__all__ = ["recompute_statistics"]
