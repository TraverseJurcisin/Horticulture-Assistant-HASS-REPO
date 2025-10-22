"""Utility helpers for BioProfile yield statistics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Iterable

from .schema import BioProfile, HarvestEvent, YieldStatistic

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017


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


def _build_stat(scope: str, profile_id: str, *, total_yield: float, total_area: float, count: int, densities: list[float]) -> YieldStatistic:
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
    return YieldStatistic(
        stat_id=f"{profile_id}:{scope}:yield",
        scope=scope,
        profile_id=profile_id,
        computed_at=_now_iso(),
        metrics=metrics,
        metadata={"source": "local_harvest_aggregation"},
    )


def recompute_statistics(profiles: Iterable[BioProfile]) -> None:
    """Rebuild species and cultivar yield statistics in-place."""

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    species_to_harvests: dict[str, list[HarvestEvent]] = defaultdict(list)

    for profile in profiles:
        harvests = list(profile.harvest_history)
        if harvests:
            total_yield, total_area, count, densities = _aggregate_harvests(harvests)
            scope = "species" if profile.profile_type == "species" else "cultivar"
            stat = _build_stat(
                scope,
                profile.profile_id,
                total_yield=total_yield,
                total_area=total_area,
                count=count,
                densities=densities,
            )
            profile.statistics = [stat]
        else:
            profile.statistics = []

        species_id = profile.species_profile_id or (profile.profile_id if profile.profile_type == "species" else None)
        if species_id:
            species_to_harvests[species_id].extend(harvests)

    for species_id, harvests in species_to_harvests.items():
        if not harvests:
            continue
        total_yield, total_area, count, densities = _aggregate_harvests(harvests)
        stat = _build_stat(
            "species",
            species_id,
            total_yield=total_yield,
            total_area=total_area,
            count=count,
            densities=densities,
        )
        target = profiles_by_id.get(species_id)
        if target is None:
            continue
        existing = [s for s in target.statistics if s.scope != "species"]
        target.statistics = existing + [stat]


__all__ = ["recompute_statistics"]
