from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import mean, median
from typing import Any

from .schema import (
    BioProfile,
    ComputedStatSnapshot,
    CultivationEvent,
    HarvestEvent,
    NutrientApplication,
    ProfileContribution,
    RunEvent,
    YieldStatistic,
)

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017
YIELD_STATS_VERSION = "yield/v1"
ENVIRONMENT_STATS_VERSION = "environment/v1"
SUCCESS_STATS_VERSION = "success/v1"
NUTRIENT_STATS_VERSION = "nutrients/v1"
EVENT_STATS_VERSION = "events/v1"
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
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return number


def _normalise_nutrient_events(
    events: Iterable[NutrientApplication],
) -> list[tuple[NutrientApplication, datetime | None]]:
    normalised: list[tuple[NutrientApplication, datetime | None]] = []
    for event in events:
        if not isinstance(event, NutrientApplication):
            continue
        timestamp = _parse_datetime(getattr(event, "applied_at", None))
        normalised.append((event, timestamp))
    normalised.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=UTC))
    return normalised


def _compute_nutrient_payload(
    events: Iterable[NutrientApplication],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    normalised = _normalise_nutrient_events(events)
    if not normalised:
        return None

    now = now or datetime.now(tz=UTC)
    product_counter: Counter[str] = Counter()
    run_ids: set[str] = set()
    total_volume = 0.0
    volume_samples = 0
    timestamps: list[datetime] = []
    intervals: list[float] = []

    previous: datetime | None = None
    for event, ts in normalised:
        key = event.product_id or event.product_name or "unspecified"
        product_counter[str(key)] += 1
        if event.run_id:
            run_ids.add(str(event.run_id))
        volume = _to_float(event.solution_volume_liters)
        if volume is not None:
            total_volume += volume
            volume_samples += 1
        if ts is not None:
            timestamps.append(ts)
            if previous is not None:
                delta = max((ts - previous).total_seconds() / 86400, 0.0)
                intervals.append(delta)
            previous = ts

    total_events = len(normalised)
    metrics: dict[str, float] = {"total_events": float(total_events)}
    if volume_samples:
        metrics["total_volume_liters"] = round(total_volume, 3)
    if run_ids:
        metrics["unique_runs"] = float(len(run_ids))
    if product_counter:
        metrics["unique_products"] = float(len(product_counter))
    if intervals:
        metrics["interval_samples"] = float(len(intervals))
        metrics["average_interval_days"] = round(mean(intervals), 3)
        metrics["median_interval_days"] = round(median(intervals), 3)

    window_counts: dict[str, int] = {}
    if timestamps:
        seven_days = now - timedelta(days=7)
        thirty_days = now - timedelta(days=30)
        window_counts["7d"] = sum(1 for ts in timestamps if ts >= seven_days)
        window_counts["30d"] = sum(1 for ts in timestamps if ts >= thirty_days)
        last_ts = timestamps[-1]
        days_since = max((now - last_ts).total_seconds() / 86400, 0.0)
        metrics["days_since_last_event"] = round(days_since, 3)
    else:
        last_ts = None

    last_event = normalised[-1][0]
    last_payload = last_event.summary()
    if last_ts is not None:
        last_payload["days_since"] = metrics.get("days_since_last_event")

    product_usage = [
        {"product": product, "count": count} for product, count in product_counter.most_common() if product and count
    ]

    payload: dict[str, Any] = {
        "metrics": metrics,
        "last_event": last_payload,
        "source": "local_nutrient_aggregation",
    }
    if product_usage:
        payload["product_usage"] = product_usage
    if intervals:
        payload["intervals"] = {
            "average_days": round(mean(intervals), 3),
            "median_days": round(median(intervals), 3),
            "samples": len(intervals),
        }
    if window_counts:
        payload["window_counts"] = window_counts
    if run_ids:
        payload["runs_touched"] = sorted(run_ids)

    return payload


def _build_nutrient_snapshot(
    profile_id: str,
    scope: str,
    events: Iterable[NutrientApplication],
    *,
    contributions: list[ProfileContribution] | None = None,
    contributor_payload: list[dict[str, Any]] | None = None,
    computed_at: str | None = None,
) -> ComputedStatSnapshot | None:
    reference_now = _parse_datetime(computed_at) if computed_at else None
    payload = _compute_nutrient_payload(events, now=reference_now)
    if payload is None:
        return None
    payload["scope"] = scope
    if contributor_payload:
        payload["contributors"] = contributor_payload
    timestamp = computed_at or _now_iso()
    return ComputedStatSnapshot(
        stats_version=NUTRIENT_STATS_VERSION,
        computed_at=timestamp,
        snapshot_id=f"{profile_id}:{NUTRIENT_STATS_VERSION}",
        payload=payload,
        contributions=contributions or [],
    )


def _normalise_cultivation_events(
    events: Iterable[CultivationEvent],
) -> list[tuple[CultivationEvent, datetime | None]]:
    ordered: list[tuple[CultivationEvent, datetime | None]] = []
    for event in events:
        if not isinstance(event, CultivationEvent):
            continue
        ts = _parse_datetime(getattr(event, "occurred_at", None))
        ordered.append((event, ts))
    ordered.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=UTC))
    return ordered


def _compute_event_payload(
    events: Iterable[CultivationEvent],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    normalised = _normalise_cultivation_events(events)
    if not normalised:
        return None

    now = now or datetime.now(tz=UTC)
    type_counter: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    run_ids: set[str] = set()
    timestamps: list[datetime] = []

    for event, ts in normalised:
        event_type = (event.event_type or "note").strip() or "note"
        type_counter[event_type] += 1
        for raw_tag in event.tags or []:
            if raw_tag is None:
                continue
            cleaned_tag = raw_tag.strip() if isinstance(raw_tag, str) else str(raw_tag).strip()
            if cleaned_tag:
                tag_counter[cleaned_tag] += 1
        if event.run_id:
            run_ids.add(str(event.run_id))
        if ts is not None:
            timestamps.append(ts)

    metrics: dict[str, float] = {"total_events": float(len(normalised))}
    if type_counter:
        metrics["unique_event_types"] = float(len(type_counter))
    if run_ids:
        metrics["unique_runs"] = float(len(run_ids))

    window_counts: dict[str, int] = {}
    last_ts: datetime | None = None
    if timestamps:
        last_ts = timestamps[-1]
        delta_days = max((now - last_ts).total_seconds() / 86400, 0.0)
        metrics["days_since_last_event"] = round(delta_days, 3)
        seven_days = now - timedelta(days=7)
        thirty_days = now - timedelta(days=30)
        window_counts["7d"] = sum(1 for ts in timestamps if ts >= seven_days)
        window_counts["30d"] = sum(1 for ts in timestamps if ts >= thirty_days)

    event_types: list[dict[str, Any]] = []
    for event_type, count in type_counter.most_common():
        payload: dict[str, Any] = {"event_type": event_type, "count": count}
        last_type_ts: datetime | None = None
        for event, ts in reversed(normalised):
            candidate_type = (event.event_type or "note").strip() or "note"
            if candidate_type == event_type:
                last_type_ts = ts
                break
        if last_type_ts is not None:
            payload["last_occurred_at"] = last_type_ts.isoformat()
            payload["days_since_last"] = round(max((now - last_type_ts).total_seconds() / 86400, 0.0), 3)
        event_types.append(payload)

    last_event = normalised[-1][0]
    last_payload = last_event.summary()
    normalised_type = (last_event.event_type or "note").strip() or "note"
    last_payload["event_type"] = normalised_type
    if last_ts is not None:
        last_payload["days_since"] = metrics.get("days_since_last_event")

    payload: dict[str, Any] = {
        "metrics": metrics,
        "last_event": last_payload,
        "event_types": event_types,
        "source": "local_event_aggregation",
    }

    if tag_counter:
        payload["top_tags"] = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common(10) if tag]
    if run_ids:
        payload["runs_touched"] = sorted(run_ids)
    if window_counts:
        payload["window_counts"] = window_counts

    return payload


def _build_event_snapshot(
    profile_id: str,
    scope: str,
    events: Iterable[CultivationEvent],
    *,
    contributions: list[ProfileContribution] | None = None,
    contributor_payload: list[dict[str, Any]] | None = None,
    computed_at: str | None = None,
) -> ComputedStatSnapshot | None:
    reference_now = _parse_datetime(computed_at) if computed_at else None
    payload = _compute_event_payload(events, now=reference_now)
    if payload is None:
        return None
    payload["scope"] = scope
    if contributor_payload:
        payload["contributors"] = contributor_payload
    timestamp = computed_at or _now_iso()
    return ComputedStatSnapshot(
        stats_version=EVENT_STATS_VERSION,
        computed_at=timestamp,
        snapshot_id=f"{profile_id}:{EVENT_STATS_VERSION}",
        payload=payload,
        contributions=contributions or [],
    )


def _aggregate_harvests(
    harvests: Iterable[HarvestEvent],
) -> tuple[float, float, int, list[float], int, int]:
    total_yield = 0.0
    total_area = 0.0
    count = 0
    fruit_total = 0
    fruit_samples = 0
    densities: list[float] = []
    for event in harvests:
        yield_value = _to_float(getattr(event, "yield_grams", None))
        if yield_value is not None:
            total_yield += yield_value
        area_value = _to_float(getattr(event, "area_m2", None))
        if area_value:
            total_area += area_value
            if yield_value is not None and area_value > 0:
                densities.append(round(yield_value / area_value, 3))
        fruit_value = getattr(event, "fruit_count", None)
        if fruit_value is not None:
            with suppress(TypeError, ValueError):
                fruit_total += int(fruit_value)
                fruit_samples += 1
        count += 1
    return total_yield, total_area, count, densities, fruit_total, fruit_samples


def _compute_harvest_windows(
    harvests: Iterable[HarvestEvent],
    *,
    now: datetime | None = None,
    windows: tuple[int, ...] = (7, 30, 90),
) -> tuple[dict[str, dict[str, Any]], datetime | None]:
    """Return rolling harvest metrics for the configured ``windows``.

    The payload mirrors the structure used by the nutrient and event trend
    calculations so the UI can display weekly and monthly production totals
    without reprocessing the full history on every render.
    """

    normalised: list[tuple[HarvestEvent, datetime | None]] = []
    for event in harvests:
        if not isinstance(event, HarvestEvent):
            continue
        timestamp = _parse_datetime(getattr(event, "harvested_at", None))
        normalised.append((event, timestamp))

    if not normalised:
        return {}, None

    normalised.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=UTC))
    now = now or datetime.now(tz=UTC)
    last_timestamp = next((ts for _event, ts in reversed(normalised) if ts is not None), None)

    window_payload: dict[str, dict[str, Any]] = {}
    for days in windows:
        threshold = now - timedelta(days=days)
        key = f"{days}d"
        window_events = [(event, ts) for event, ts in normalised if ts is not None and ts >= threshold]
        if not window_events:
            continue

        total_yield = 0.0
        total_area = 0.0
        fruit_total = 0
        fruit_samples = 0
        densities: list[float] = []
        for event, _ts in window_events:
            yield_value = _to_float(getattr(event, "yield_grams", None))
            if yield_value is not None:
                total_yield += yield_value
            area_value = _to_float(getattr(event, "area_m2", None))
            if area_value:
                total_area += area_value
                if yield_value is not None and area_value > 0:
                    densities.append(round(yield_value / area_value, 3))
            fruit_value = getattr(event, "fruit_count", None)
            if fruit_value is not None:
                try:
                    fruit_total += int(fruit_value)
                    fruit_samples += 1
                except (TypeError, ValueError):
                    continue

        payload: dict[str, Any] = {
            "harvest_count": float(len(window_events)),
            "total_yield_grams": round(total_yield, 3),
        }
        if window_events:
            payload["average_yield_grams"] = round(
                total_yield / len(window_events),
                3,
            )
        if total_area:
            payload["total_area_m2"] = round(total_area, 3)
            payload["average_yield_density_g_m2"] = round(total_yield / total_area, 3)
        if densities:
            payload["mean_density_g_m2"] = round(mean(densities), 3)
        if fruit_samples:
            payload["fruit_count"] = float(fruit_total)

        last_ts = window_events[-1][1]
        if last_ts is not None:
            payload["last_harvest_at"] = last_ts.isoformat()
            delta = max((now - last_ts).total_seconds() / 86400, 0.0)
            payload["days_since_last"] = round(delta, 3)

        window_payload[key] = payload

    return window_payload, last_timestamp


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

        timestamp = computed_at or _now_iso()

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
                    computed_at=timestamp,
                    n_runs=summary.run_count or None,
                    weight=round(weight, 6) if weight is not None else None,
                )
            )

        payload["contributors"] = contributor_payload

        return ComputedStatSnapshot(
            stats_version=ENVIRONMENT_STATS_VERSION,
            computed_at=timestamp,
            snapshot_id=f"{self.species_id}:{ENVIRONMENT_STATS_VERSION}",
            payload=payload,
            contributions=contributions,
        )


@dataclass
class _SuccessSummary:
    profile_id: str
    profile_type: str
    ratio_sum: float = 0.0
    ratio_count: int = 0
    weighted_met: float = 0.0
    weighted_total: float = 0.0
    sample_count: int = 0
    stress_events: int = 0
    best_ratio: float | None = None
    worst_ratio: float | None = None
    run_ids: set[str] = field(default_factory=set)

    def add_sample(
        self,
        ratio: float,
        *,
        weight: float | None = None,
        stress: int | None = None,
    ) -> None:
        ratio = max(0.0, min(1.0, ratio))
        self.sample_count += 1
        self.ratio_sum += ratio
        self.ratio_count += 1
        if weight is not None and weight > 0:
            self.weighted_met += ratio * weight
            self.weighted_total += weight
        if stress is not None:
            stress_value = max(0, stress)
            if stress_value:
                self.stress_events += stress_value
        self.best_ratio = ratio if self.best_ratio is None else max(self.best_ratio, ratio)
        self.worst_ratio = ratio if self.worst_ratio is None else min(self.worst_ratio, ratio)

    def average_ratio(self) -> float | None:
        if not self.ratio_count:
            return None
        return self.ratio_sum / self.ratio_count

    def weighted_ratio(self) -> float | None:
        if self.weighted_total > 0:
            return self.weighted_met / self.weighted_total
        return self.average_ratio()

    def to_payload(self, scope: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scope": scope,
            "samples_recorded": self.sample_count,
            "runs_tracked": len(self.run_ids),
            "source": "local_success_aggregation",
        }
        avg = self.average_ratio()
        if avg is not None:
            payload["average_success_percent"] = round(avg * 100, 3)
        weighted = self.weighted_ratio()
        if weighted is not None:
            payload["weighted_success_percent"] = round(weighted * 100, 3)
        if self.best_ratio is not None:
            payload["best_success_percent"] = round(self.best_ratio * 100, 3)
        if self.worst_ratio is not None:
            payload["worst_success_percent"] = round(self.worst_ratio * 100, 3)
        if self.weighted_total:
            payload["targets_total"] = round(self.weighted_total, 3)
            payload["targets_met"] = round(self.weighted_met, 3)
        if self.stress_events:
            payload["stress_events"] = self.stress_events
        return payload

    def contribution_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "samples_recorded": self.sample_count,
            "runs_tracked": len(self.run_ids),
        }
        avg = self.average_ratio()
        if avg is not None:
            payload["average_success_percent"] = round(avg * 100, 3)
        weighted = self.weighted_ratio()
        if weighted is not None:
            payload["weighted_success_percent"] = round(weighted * 100, 3)
        if self.weighted_total:
            payload["targets_total"] = round(self.weighted_total, 3)
            payload["targets_met"] = round(self.weighted_met, 3)
        if self.stress_events:
            payload["stress_events"] = self.stress_events
        if self.best_ratio is not None:
            payload["best_success_percent"] = round(self.best_ratio * 100, 3)
        if self.worst_ratio is not None:
            payload["worst_success_percent"] = round(self.worst_ratio * 100, 3)
        return payload


@dataclass
class _SuccessAggregate:
    species_id: str
    summaries: list[_SuccessSummary] = field(default_factory=list)
    ratio_sum: float = 0.0
    ratio_count: int = 0
    weighted_met: float = 0.0
    weighted_total: float = 0.0
    sample_count: int = 0
    stress_events: int = 0
    run_ids: set[str] = field(default_factory=set)
    best_ratio: float | None = None
    worst_ratio: float | None = None

    def merge(self, summary: _SuccessSummary) -> None:
        self.summaries.append(summary)
        self.ratio_sum += summary.ratio_sum
        self.ratio_count += summary.ratio_count
        self.weighted_met += summary.weighted_met
        self.weighted_total += summary.weighted_total
        self.sample_count += summary.sample_count
        self.stress_events += summary.stress_events
        self.run_ids.update(summary.run_ids)
        if summary.best_ratio is not None:
            self.best_ratio = (
                summary.best_ratio if self.best_ratio is None else max(self.best_ratio, summary.best_ratio)
            )
        if summary.worst_ratio is not None:
            self.worst_ratio = (
                summary.worst_ratio if self.worst_ratio is None else min(self.worst_ratio, summary.worst_ratio)
            )

    def average_ratio(self) -> float | None:
        if not self.ratio_count:
            return None
        return self.ratio_sum / self.ratio_count

    def weighted_ratio(self) -> float | None:
        if self.weighted_total > 0:
            return self.weighted_met / self.weighted_total
        return self.average_ratio()

    def build_snapshot(self, computed_at: str | None = None) -> ComputedStatSnapshot | None:
        if not self.sample_count:
            return None

        timestamp = computed_at or _now_iso()
        payload: dict[str, Any] = {
            "scope": "species",
            "samples_recorded": self.sample_count,
            "runs_tracked": len(self.run_ids),
            "source": "local_success_aggregation",
        }
        avg = self.average_ratio()
        if avg is not None:
            payload["average_success_percent"] = round(avg * 100, 3)
        weighted = self.weighted_ratio()
        if weighted is not None:
            payload["weighted_success_percent"] = round(weighted * 100, 3)
        if self.best_ratio is not None:
            payload["best_success_percent"] = round(self.best_ratio * 100, 3)
        if self.worst_ratio is not None:
            payload["worst_success_percent"] = round(self.worst_ratio * 100, 3)
        if self.weighted_total:
            payload["targets_total"] = round(self.weighted_total, 3)
            payload["targets_met"] = round(self.weighted_met, 3)
        if self.stress_events:
            payload["stress_events"] = self.stress_events

        contributors_payload = [summary.contribution_payload() for summary in self.summaries]
        if contributors_payload:
            payload["contributors"] = contributors_payload

        contributions: list[ProfileContribution] = []
        denom = self.weighted_total if self.weighted_total > 0 else float(self.sample_count or 0)
        for summary in self.summaries:
            numerator = summary.weighted_total if self.weighted_total > 0 else float(summary.sample_count)
            weight = None
            if denom and numerator:
                weight = round(numerator / denom, 6)
            contributions.append(
                ProfileContribution(
                    profile_id=self.species_id,
                    child_id=summary.profile_id,
                    stats_version=SUCCESS_STATS_VERSION,
                    computed_at=timestamp,
                    n_runs=len(summary.run_ids) or (summary.sample_count or None),
                    weight=weight,
                )
            )

        snapshot = ComputedStatSnapshot(
            stats_version=SUCCESS_STATS_VERSION,
            computed_at=timestamp,
            snapshot_id=f"{self.species_id}:{SUCCESS_STATS_VERSION}",
            payload=payload,
            contributions=contributions,
        )
        return snapshot


_RATIO_NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_FRACTION_PATTERN = re.compile(
    r"(?P<numerator>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*/\s*(?P<denominator>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)


def _coerce_ratio_value(value: Any) -> float | None:
    """Return ``value`` coerced to a 0-1 ratio when possible."""

    percent_notation = False
    number = _to_float(value)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("%"):
            percent_notation = True
            text = text[:-1]
        fraction_match = _FRACTION_PATTERN.search(text)
        if fraction_match:
            numerator = _to_float(fraction_match.group("numerator"))
            denominator = _to_float(fraction_match.group("denominator"))
            if numerator is not None and denominator is not None and denominator != 0:
                ratio = numerator / denominator
                return max(0.0, min(1.0, ratio))
        if number is None:
            match = _RATIO_NUMBER_PATTERN.search(text)
            if match:
                number = _to_float(match.group(0))

    if number is None:
        return None

    if percent_notation or number > 1.0:
        number = number / 100.0

    return max(0.0, min(1.0, number))


def _extract_success_metrics(event: RunEvent) -> tuple[float, float | None, int | None] | None:
    metadata = event.metadata if isinstance(event.metadata, dict) else {}

    def _lookup(primary: Any | None, *keys: str) -> Any | None:
        if primary is not None:
            return primary
        for key in keys:
            if key in metadata and metadata[key] is not None:
                return metadata[key]
        return None

    stress_raw = _lookup(event.stress_events, "stress_events", "stress_count", "alert_count")
    stress_float = _to_float(stress_raw)
    stress_value = int(stress_float) if stress_float is not None else None

    targets_met_raw = _lookup(event.targets_met, "targets_met", "targets_hit", "on_target_samples")
    targets_total_raw = _lookup(event.targets_total, "targets_total", "targets_expected", "total_samples")
    met = _to_float(targets_met_raw)
    total = _to_float(targets_total_raw)
    if met is not None and total is not None and total > 0:
        ratio = met / total
        ratio = max(0.0, min(1.0, ratio))
        return ratio, total, stress_value

    success_raw = _lookup(
        event.success_rate,
        "success_rate",
        "success_percent",
        "compliance_ratio",
        "compliance",
    )
    success = _coerce_ratio_value(success_raw)
    if success is None:
        return None
    return success, None, stress_value


def _compute_success_snapshot(profile: BioProfile) -> tuple[ComputedStatSnapshot, _SuccessSummary] | None:
    if not profile.run_history:
        return None

    summary = _SuccessSummary(profile_id=profile.profile_id, profile_type=profile.profile_type)
    for event in profile.run_history:
        metrics = _extract_success_metrics(event)
        if metrics is None:
            continue
        ratio, weight, stress = metrics
        if event.run_id is not None:
            run_id = str(event.run_id).strip()
            if run_id:
                summary.run_ids.add(run_id)
        summary.add_sample(ratio, weight=weight, stress=stress)

    if not summary.sample_count:
        return None

    scope = "species" if profile.profile_type == "species" else "cultivar"
    computed_at = _now_iso()
    payload = summary.to_payload(scope)
    snapshot = ComputedStatSnapshot(
        stats_version=SUCCESS_STATS_VERSION,
        computed_at=computed_at,
        snapshot_id=f"{profile.profile_id}:{SUCCESS_STATS_VERSION}",
        payload=payload,
        contributions=[],
    )
    return snapshot, summary


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
        if isinstance(env, Mapping):
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

    profile_list = list(profiles)
    profiles_by_id = {profile.profile_id: profile for profile in profile_list}
    species_to_harvests: defaultdict[str, list[HarvestEvent]] = defaultdict(list)
    species_breakdown: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    species_environment: dict[str, _EnvironmentAggregate] = {}
    species_success: dict[str, _SuccessAggregate] = {}
    species_nutrient_events: defaultdict[str, list[NutrientApplication]] = defaultdict(list)
    species_nutrient_breakdown: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    species_event_history: defaultdict[str, list[CultivationEvent]] = defaultdict(list)
    species_event_breakdown: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for profile in profile_list:
        harvests = list(profile.harvest_history)
        run_ids = {str(event.run_id).strip() for event in harvests if getattr(event, "run_id", None)}
        run_ids = {run_id for run_id in run_ids if run_id}
        if not run_ids:
            run_ids = {str(event.run_id).strip() for event in profile.run_history if getattr(event, "run_id", None)}
            run_ids = {run_id for run_id in run_ids if run_id}
        run_count = len(run_ids)

        nutrient_events = list(profile.nutrient_history)
        nutrient_scope = "species" if profile.profile_type == "species" else "cultivar"
        nutrient_snapshot = _build_nutrient_snapshot(
            profile.profile_id,
            nutrient_scope,
            nutrient_events,
        )
        _replace_snapshot(profile, NUTRIENT_STATS_VERSION, nutrient_snapshot)

        cultivation_events = list(profile.event_history)
        event_scope = "species" if profile.profile_type == "species" else "cultivar"
        event_snapshot = _build_event_snapshot(
            profile.profile_id,
            event_scope,
            cultivation_events,
        )
        _replace_snapshot(profile, EVENT_STATS_VERSION, event_snapshot)

        aggregate: dict[str, Any] | None = None
        if harvests:
            (
                total_yield,
                total_area,
                count,
                densities,
                fruit_total,
                fruit_samples,
            ) = _aggregate_harvests(harvests)
            scope = "species" if profile.profile_type == "species" else "cultivar"
            now = datetime.now(tz=UTC)
            window_totals, last_harvest_ts = _compute_harvest_windows(harvests, now=now)
            computed_at = now.isoformat()
            stat = _build_stat(
                scope,
                profile.profile_id,
                total_yield=total_yield,
                total_area=total_area,
                count=count,
                densities=densities,
                computed_at=computed_at,
            )
            if last_harvest_ts is not None:
                delta = max((now - last_harvest_ts).total_seconds() / 86400, 0.0)
                stat.metrics["days_since_last_harvest"] = round(delta, 3)
                stat.metadata.setdefault("last_harvest_at", last_harvest_ts.isoformat())
            if fruit_samples:
                stat.metrics["total_fruit_count"] = float(fruit_total)
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
            if stat.metadata.get("last_harvest_at"):
                snapshot_payload["last_harvest_at"] = stat.metadata["last_harvest_at"]
            if stat.metrics.get("days_since_last_harvest") is not None:
                snapshot_payload["days_since_last_harvest"] = stat.metrics["days_since_last_harvest"]
            if fruit_samples:
                yields_payload = snapshot_payload.setdefault("yields", {})
                yields_payload["total_fruit_count"] = fruit_total
            if window_totals:
                snapshot_payload["window_totals"] = window_totals
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
                "run_ids": sorted(run_ids),
            }
            if stat.metrics.get("days_since_last_harvest") is not None:
                aggregate["days_since_last_harvest"] = stat.metrics["days_since_last_harvest"]
            if fruit_samples:
                aggregate["fruit_count"] = fruit_total
            if window_totals:
                aggregate["window_totals"] = window_totals
            if stat.metadata.get("last_harvest_at"):
                aggregate["last_harvest_at"] = stat.metadata["last_harvest_at"]
        else:
            profile.statistics = []
            _replace_snapshot(profile, YIELD_STATS_VERSION, None)

        species_id = profile.species_profile_id or (profile.profile_id if profile.profile_type == "species" else None)
        if species_id:
            species_to_harvests[species_id].extend(harvests)
            if aggregate is not None:
                species_breakdown[species_id].append(aggregate)
            if nutrient_events:
                species_nutrient_events[species_id].extend(nutrient_events)
                total_volume = 0.0
                volume_samples = 0
                for event in nutrient_events:
                    volume = _to_float(getattr(event, "solution_volume_liters", None))
                    if volume is not None:
                        total_volume += volume
                        volume_samples += 1
                normalised_events = _normalise_nutrient_events(nutrient_events)
                last_ts = normalised_events[-1][1] if normalised_events else None
                contributor_payload = {
                    "profile_id": profile.profile_id,
                    "profile_type": profile.profile_type,
                    "event_count": len(nutrient_events),
                }
                if volume_samples:
                    contributor_payload["total_volume_liters"] = round(total_volume, 3)
                if last_ts is not None:
                    contributor_payload["last_applied_at"] = last_ts.isoformat()
                species_nutrient_breakdown[species_id].append(contributor_payload)
            if cultivation_events:
                species_event_history[species_id].extend(cultivation_events)
                breakdown_payload: dict[str, Any] = {
                    "profile_id": profile.profile_id,
                    "profile_type": profile.profile_type,
                    "event_count": len(cultivation_events),
                }
                if event_snapshot and isinstance(event_snapshot.payload, dict):
                    last_event_payload = event_snapshot.payload.get("last_event")
                    if isinstance(last_event_payload, dict) and last_event_payload:
                        breakdown_payload["last_event"] = last_event_payload
                species_event_breakdown[species_id].append(breakdown_payload)

        success_snapshot = _compute_success_snapshot(profile)
        if success_snapshot is not None:
            snapshot, success_summary = success_snapshot
            _replace_snapshot(profile, SUCCESS_STATS_VERSION, snapshot)
            if species_id:
                aggregate_success = species_success.get(species_id)
                if aggregate_success is None:
                    aggregate_success = _SuccessAggregate(species_id=species_id)
                    species_success[species_id] = aggregate_success
                aggregate_success.merge(success_summary)
        else:
            _replace_snapshot(profile, SUCCESS_STATS_VERSION, None)

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
        (
            total_yield,
            total_area,
            count,
            densities,
            fruit_total,
            fruit_samples,
        ) = _aggregate_harvests(harvests)
        now = datetime.now(tz=UTC)
        window_totals, last_harvest_ts = _compute_harvest_windows(harvests, now=now)
        computed_at = now.isoformat()
        stat = _build_stat(
            "species",
            species_id,
            total_yield=total_yield,
            total_area=total_area,
            count=count,
            densities=densities,
            computed_at=computed_at,
        )
        if last_harvest_ts is not None:
            delta = max((now - last_harvest_ts).total_seconds() / 86400, 0.0)
            stat.metrics["days_since_last_harvest"] = round(delta, 3)
            stat.metadata.setdefault("last_harvest_at", last_harvest_ts.isoformat())
        if fruit_samples:
            stat.metrics["total_fruit_count"] = float(fruit_total)

        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        existing = [s for s in target.statistics if s.scope != "species"]
        target.statistics = existing + [stat]

        contributors: list[ProfileContribution] = []
        contributor_payload: list[dict[str, Any]] = []
        for item in species_breakdown.get(species_id, []):
            weight = (item["total_yield"] / total_yield) if total_yield else None
            contributor = ProfileContribution(
                profile_id=species_id,
                child_id=item["child_id"],
                stats_version=YIELD_STATS_VERSION,
                computed_at=computed_at,
                n_runs=len(item.get("run_ids") or ()) or None,
                weight=round(weight, 6) if weight is not None else None,
            )
            contributors.append(contributor)
            payload: dict[str, Any] = {
                "profile_id": item["child_id"],
                "harvest_count": item["harvest_count"],
                "total_yield_grams": round(item["total_yield"], 3),
                "total_area_m2": round(item["total_area"], 3),
                "mean_density_g_m2": item["mean_density"],
                "runs_tracked": len(item.get("run_ids") or ()),
            }
            if "fruit_count" in item:
                payload["total_fruit_count"] = item["fruit_count"]
            if item.get("days_since_last_harvest") is not None:
                payload["days_since_last_harvest"] = item["days_since_last_harvest"]
            if item.get("last_harvest_at"):
                payload["last_harvest_at"] = item["last_harvest_at"]
            if item.get("window_totals"):
                payload["window_totals"] = item["window_totals"]
            contributor_payload.append(payload)

        species_run_ids = {str(event.run_id).strip() for event in harvests if getattr(event, "run_id", None)}
        species_run_ids = {run_id for run_id in species_run_ids if run_id}
        for item in species_breakdown.get(species_id, []):
            for run_id in item.get("run_ids") or ():
                text = str(run_id).strip()
                if text:
                    species_run_ids.add(text)
        metrics = dict(stat.metrics)
        snapshot_payload: dict[str, Any] = {
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
        if stat.metadata.get("last_harvest_at"):
            snapshot_payload["last_harvest_at"] = stat.metadata["last_harvest_at"]
        if metrics.get("days_since_last_harvest") is not None:
            snapshot_payload["days_since_last_harvest"] = metrics["days_since_last_harvest"]
        if fruit_samples:
            snapshot_payload.setdefault("yields", {})["total_fruit_count"] = fruit_total
        if window_totals:
            snapshot_payload["window_totals"] = window_totals

        snapshot = ComputedStatSnapshot(
            stats_version=YIELD_STATS_VERSION,
            computed_at=computed_at,
            snapshot_id=f"{species_id}:{YIELD_STATS_VERSION}",
            payload=snapshot_payload,
            contributions=contributors,
        )
        _replace_snapshot(target, YIELD_STATS_VERSION, snapshot)

    for species_id, events in species_event_history.items():
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        timestamp = _now_iso()
        breakdown = species_event_breakdown.get(species_id, [])
        total_events = sum(item.get("event_count", 0) for item in breakdown)
        contributions: list[ProfileContribution] = []
        contributor_payload: list[dict[str, Any]] = []
        for item in breakdown:
            child_id = item.get("profile_id")
            payload = {k: v for k, v in item.items() if v not in (None, [], {}, 0, 0.0, "")}
            contributor_payload.append(payload)
            weight = (item.get("event_count") / total_events) if total_events else None
            if child_id:
                contributions.append(
                    ProfileContribution(
                        profile_id=species_id,
                        child_id=str(child_id),
                        stats_version=EVENT_STATS_VERSION,
                        computed_at=timestamp,
                        n_runs=item.get("event_count") or None,
                        weight=round(weight, 6) if weight is not None else None,
                    )
                )

        snapshot = _build_event_snapshot(
            species_id,
            "species",
            events,
            contributions=[contrib for contrib in contributions if contrib.child_id],
            contributor_payload=[payload for payload in contributor_payload if payload],
            computed_at=timestamp,
        )
        _replace_snapshot(target, EVENT_STATS_VERSION, snapshot)

    for species_id, events in species_nutrient_events.items():
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        timestamp = _now_iso()
        breakdown = species_nutrient_breakdown.get(species_id, [])
        total_events = sum(item.get("event_count", 0) for item in breakdown)
        contributions: list[ProfileContribution] = []
        contributor_payload: list[dict[str, Any]] = []
        for item in breakdown:
            raw_child_id = item.get("profile_id")
            child_id = raw_child_id.strip() if isinstance(raw_child_id, str) else raw_child_id
            payload: dict[str, Any] = {}
            if isinstance(child_id, str) and child_id:
                payload["profile_id"] = child_id
            profile_type = item.get("profile_type")
            if isinstance(profile_type, str) and profile_type:
                payload["profile_type"] = profile_type
            event_count = item.get("event_count")
            if event_count is not None:
                payload["event_count"] = event_count
            if "total_volume_liters" in item and item["total_volume_liters"] is not None:
                payload["total_volume_liters"] = item["total_volume_liters"]
            last_applied = item.get("last_applied_at")
            if isinstance(last_applied, str) and last_applied:
                payload["last_applied_at"] = last_applied
            if payload:
                contributor_payload.append(payload)
            weight = (event_count / total_events) if total_events and event_count is not None else None
            if isinstance(child_id, str):
                if child_id:
                    contributions.append(
                        ProfileContribution(
                            profile_id=species_id,
                            child_id=child_id,
                            stats_version=NUTRIENT_STATS_VERSION,
                            computed_at=timestamp,
                            n_runs=event_count or None,
                            weight=round(weight, 6) if weight is not None else None,
                        )
                    )
            elif child_id:
                contributions.append(
                    ProfileContribution(
                        profile_id=species_id,
                        child_id=str(child_id),
                        stats_version=NUTRIENT_STATS_VERSION,
                        computed_at=timestamp,
                        n_runs=event_count or None,
                        weight=round(weight, 6) if weight is not None else None,
                    )
                )

        snapshot = _build_nutrient_snapshot(
            species_id,
            "species",
            events,
            contributions=[contrib for contrib in contributions if contrib.child_id],
            contributor_payload=[payload for payload in contributor_payload if payload],
            computed_at=timestamp,
        )
        _replace_snapshot(target, NUTRIENT_STATS_VERSION, snapshot)

    for profile in profile_list:
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

    for species_id, aggregate in species_success.items():
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        snapshot = aggregate.build_snapshot()
        if snapshot is None:
            _replace_snapshot(target, SUCCESS_STATS_VERSION, None)
            continue
        _replace_snapshot(target, SUCCESS_STATS_VERSION, snapshot)
        target.refresh_sections()


__all__ = [
    "recompute_statistics",
    "SUCCESS_STATS_VERSION",
    "NUTRIENT_STATS_VERSION",
]
