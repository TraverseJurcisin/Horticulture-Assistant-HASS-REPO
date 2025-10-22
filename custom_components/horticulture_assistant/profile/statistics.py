from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
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
ENVIRONMENT_STATS_VERSION = "environment/v1"
ENVIRONMENT_FIELDS: dict[str, str] = {
    "temperature_c": "avg_temperature_c",
    "humidity_percent": "avg_humidity_percent",
    "co2_ppm": "avg_co2_ppm",
    "vpd_kpa": "avg_vpd_kpa",
    "dli_mol_m2_day": "avg_dli_mol_m2_day",
    "ppfd_umol_m2_s": "avg_ppfd_umol_m2_s",
}


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


@dataclass
class _EnvironmentSummary:
    profile_id: str
    profile_type: str
    run_count: int
    metric_sums: dict[str, float]
    metric_counts: dict[str, int]
    total_duration_days: float
    duration_samples: int
    max_duration_days: float
    averages: dict[str, float]


@dataclass
class _EnvironmentAggregate:
    species_id: str
    metric_sums: dict[str, float]
    metric_counts: dict[str, int]
    total_duration_days: float = 0.0
    duration_samples: int = 0
    max_duration_days: float = 0.0
    run_count: int = 0
    contributors: list[_EnvironmentSummary] | None = None

    def merge(self, summary: _EnvironmentSummary) -> None:
        for key, value in summary.metric_sums.items():
            self.metric_sums[key] = self.metric_sums.get(key, 0.0) + value
        for key, value in summary.metric_counts.items():
            self.metric_counts[key] = self.metric_counts.get(key, 0) + value
        self.total_duration_days += summary.total_duration_days
        self.duration_samples += summary.duration_samples
        self.max_duration_days = max(self.max_duration_days, summary.max_duration_days)
        self.run_count += summary.run_count
        if self.contributors is None:
            self.contributors = []
        self.contributors.append(summary)

    def build_snapshot(self, computed_at: str | None = None) -> ComputedStatSnapshot | None:
        if not self.run_count and not any(self.metric_counts.values()) and self.duration_samples == 0:
            return None

        metrics: dict[str, float] = {}
        for key, count in self.metric_counts.items():
            if not count:
                continue
            metrics[key] = round(self.metric_sums.get(key, 0.0) / count, 3)

        payload: dict[str, Any] = {
            "scope": "species",
            "metrics": metrics,
            "runs_recorded": self.run_count,
        }

        if self.duration_samples:
            mean_duration = self.total_duration_days / self.duration_samples if self.duration_samples else 0.0
            payload["durations"] = {
                "total_days": round(self.total_duration_days, 3),
                "mean_days": round(mean_duration, 3),
                "max_days": round(self.max_duration_days, 3),
            }

        payload["samples"] = {key: count for key, count in self.metric_counts.items() if count}

        contributions: list[ProfileContribution] = []
        contributor_payload: list[dict[str, Any]] = []
        total_runs = sum(summary.run_count for summary in self.contributors or [])
        for summary in self.contributors or []:
            contributor_payload.append(
                {
                    "profile_id": summary.profile_id,
                    "profile_type": summary.profile_type,
                    "runs_recorded": summary.run_count,
                    "averages": summary.averages,
                }
            )
            weight = (summary.run_count / total_runs) if total_runs else None
            contributions.append(
                ProfileContribution(
                    profile_id=self.species_id,
                    child_id=summary.profile_id,
                    stats_version=ENVIRONMENT_STATS_VERSION,
                    computed_at=computed_at,
                    n_runs=summary.run_count or None,
                    weight=round(weight, 6) if weight is not None else None,
                )
            )

        payload["contributors"] = contributor_payload

        timestamp = computed_at or _now_iso()
        return ComputedStatSnapshot(
            stats_version=ENVIRONMENT_STATS_VERSION,
            computed_at=timestamp,
            snapshot_id=f"{self.species_id}:{ENVIRONMENT_STATS_VERSION}",
            payload=payload,
            contributions=contributions,
        )


def _compute_environment_snapshot(profile: BioProfile) -> tuple[ComputedStatSnapshot, _EnvironmentSummary] | None:
    runs = list(profile.run_history)
    if not runs:
        return None

    metric_sums: dict[str, float] = defaultdict(float)
    metric_counts: dict[str, int] = defaultdict(int)
    durations: list[float] = []
    run_count = len(runs)

    for event in runs:
        env = event.environment
        if isinstance(env, dict):
            for raw_key, metric_key in ENVIRONMENT_FIELDS.items():
                value = _to_float(env.get(raw_key))
                if value is None:
                    continue
                metric_sums[metric_key] += value
                metric_counts[metric_key] += 1

        start = _parse_datetime(event.started_at)
        end = _parse_datetime(event.ended_at)
        if start is not None and end is None:
            end = datetime.now(tz=UTC)
        if start is not None and end is not None and end >= start:
            duration = (end - start).total_seconds() / 86400
            if duration >= 0:
                durations.append(duration)

    averages: dict[str, float] = {}
    for key, count in metric_counts.items():
        if not count:
            continue
        averages[key] = round(metric_sums[key] / count, 3)

    payload: dict[str, Any] = {
        "scope": "species" if profile.profile_type == "species" else "cultivar",
        "metrics": averages,
        "runs_recorded": run_count,
        "samples": {key: count for key, count in metric_counts.items() if count},
    }

    if durations:
        payload["durations"] = {
            "total_days": round(sum(durations), 3),
            "mean_days": round(sum(durations) / len(durations), 3),
            "max_days": round(max(durations), 3),
        }

    computed_at = _now_iso()
    snapshot = ComputedStatSnapshot(
        stats_version=ENVIRONMENT_STATS_VERSION,
        computed_at=computed_at,
        snapshot_id=f"{profile.profile_id}:{ENVIRONMENT_STATS_VERSION}",
        payload=payload,
        contributions=[],
    )

    summary = _EnvironmentSummary(
        profile_id=profile.profile_id,
        profile_type=profile.profile_type,
        run_count=run_count,
        metric_sums=dict(metric_sums),
        metric_counts=dict(metric_counts),
        total_duration_days=sum(durations),
        duration_samples=len(durations),
        max_duration_days=max(durations) if durations else 0.0,
        averages=averages,
    )

    return snapshot, summary


def recompute_statistics(profiles: Iterable[BioProfile]) -> None:
    """Rebuild species and cultivar yield statistics in-place."""

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    species_to_harvests: defaultdict[str, list[HarvestEvent]] = defaultdict(list)
    species_breakdown: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    species_environment: dict[str, _EnvironmentAggregate] = {}

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

        env_snapshot = _compute_environment_snapshot(profile)
        if env_snapshot is not None:
            snapshot, summary = env_snapshot
            _replace_snapshot(profile, ENVIRONMENT_STATS_VERSION, snapshot)
            if species_id:
                aggregate_env = species_environment.get(species_id)
                if aggregate_env is None:
                    aggregate_env = _EnvironmentAggregate(
                        species_id=species_id,
                        metric_sums={},
                        metric_counts={},
                    )
                    species_environment[species_id] = aggregate_env
                aggregate_env.merge(summary)
        else:
            _replace_snapshot(profile, ENVIRONMENT_STATS_VERSION, None)

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

    for species_id, aggregate in species_environment.items():
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        snapshot = aggregate.build_snapshot()
        if snapshot is None:
            _replace_snapshot(target, ENVIRONMENT_STATS_VERSION, None)
            continue
        _replace_snapshot(target, ENVIRONMENT_STATS_VERSION, snapshot)
        target.refresh_sections()


__all__ = ["recompute_statistics"]
