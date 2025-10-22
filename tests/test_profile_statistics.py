import pytest

from custom_components.horticulture_assistant.profile.schema import BioProfile, HarvestEvent
from custom_components.horticulture_assistant.profile.statistics import recompute_statistics


def test_recompute_statistics_handles_zero_area():
    species = BioProfile(profile_id="species", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species",
    )

    cultivar.add_harvest_event(
        HarvestEvent(
            harvest_id="h1",
            profile_id="cultivar",
            species_id="species",
            run_id="run-1",
            harvested_at="2024-01-01T00:00:00Z",
            yield_grams=100.0,
            area_m2=2.0,
        )
    )
    cultivar.add_harvest_event(
        HarvestEvent(
            harvest_id="h2",
            profile_id="cultivar",
            species_id="species",
            run_id="run-1",
            harvested_at="2024-01-08T00:00:00Z",
            yield_grams=50.0,
            area_m2=None,
        )
    )
    species.add_harvest_event(
        HarvestEvent(
            harvest_id="s1",
            profile_id="species",
            species_id="species",
            run_id=None,
            harvested_at="2024-01-05T00:00:00Z",
            yield_grams=80.0,
            area_m2=0.0,
        )
    )

    recompute_statistics([species, cultivar])

    cultivar_stats = cultivar.statistics[0]
    assert cultivar_stats.scope == "cultivar"
    assert cultivar_stats.metrics["harvest_count"] == 2
    assert cultivar_stats.metrics["total_yield_grams"] == 150.0
    assert cultivar_stats.metrics["total_area_m2"] == 2.0
    assert cultivar_stats.metrics["average_yield_density_g_m2"] == 75.0
    assert cultivar_stats.metrics["mean_density_g_m2"] == 50.0

    cultivar_snapshot = next(
        (snap for snap in cultivar.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert cultivar_snapshot is not None
    assert cultivar_snapshot.payload["harvest_count"] == 2
    assert cultivar_snapshot.payload["yields"]["total_grams"] == pytest.approx(150.0)
    assert cultivar_snapshot.payload["runs_tracked"] == 1

    species_stats = species.statistics[-1]
    assert species_stats.scope == "species"
    assert species_stats.metrics["total_yield_grams"] == 230.0
    assert species_stats.metrics["total_area_m2"] == 2.0
    assert species_stats.metrics["average_yield_density_g_m2"] == 115.0
    assert species_stats.metrics["mean_density_g_m2"] == 50.0

    species_snapshot = next(
        (snap for snap in species.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert species_snapshot is not None
    assert species_snapshot.payload["harvest_count"] == 3
    assert species_snapshot.payload["yields"]["total_grams"] == pytest.approx(230.0)
    assert species_snapshot.payload["runs_tracked"] == 1
    contributors = {item["profile_id"]: item for item in species_snapshot.payload["contributors"]}
    assert contributors["cultivar"]["total_yield_grams"] == pytest.approx(150.0)
    contribution = next(contrib for contrib in species_snapshot.contributions if contrib.child_id == "cultivar")
    assert contribution.weight == pytest.approx(150.0 / 230.0)
    assert contribution.n_runs == 1


def test_recompute_statistics_handles_profiles_without_harvests():
    profile = BioProfile(profile_id="empty", display_name="Empty")
    recompute_statistics([profile])
    assert profile.statistics == []
    assert profile.computed_stats == []
