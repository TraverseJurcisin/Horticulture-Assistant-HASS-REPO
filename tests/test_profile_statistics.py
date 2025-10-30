import datetime as dt

import pytest

from custom_components.horticulture_assistant.profile.schema import (
    BioProfile,
    CultivationEvent,
    HarvestEvent,
    NutrientApplication,
    RunEvent,
)
from custom_components.horticulture_assistant.profile.statistics import (
    _build_event_snapshot,
    _build_nutrient_snapshot,
    _compute_nutrient_payload,
    recompute_statistics,
)


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


def test_compute_nutrient_payload_normalises_identifiers():
    events = [
        NutrientApplication(
            event_id="n1",
            profile_id="cultivar",
            species_id="species",
            run_id=" run-1 ",
            applied_at="2024-01-01T00:00:00Z",
            product_id=" product-1 ",
            solution_volume_liters=1.0,
        ),
        NutrientApplication(
            event_id="n2",
            profile_id="cultivar",
            species_id="species",
            run_id="run-1",
            applied_at="2024-01-02T00:00:00Z",
            product_id="product-1",
            solution_volume_liters=2.0,
        ),
    ]

    payload = _compute_nutrient_payload(events, now=dt.datetime(2024, 1, 3, tzinfo=dt.UTC))

    assert payload is not None
    assert payload["metrics"]["unique_products"] == 1.0
    assert payload["product_usage"] == [{"product": "product-1", "count": 2}]
    assert payload.get("runs_touched") == ["run-1"]


def test_recompute_statistics_handles_profiles_without_harvests():
    profile = BioProfile(profile_id="empty", display_name="Empty")
    recompute_statistics([profile])
    assert profile.statistics == []
    assert all(snapshot.stats_version != "yield/v1" for snapshot in profile.computed_stats)


def test_recompute_statistics_ignores_invalid_fruit_count_without_skipping_event():
    profile = BioProfile(profile_id="plant", display_name="Plant")
    profile.add_harvest_event(
        HarvestEvent(
            harvest_id="h1",
            profile_id="plant",
            species_id=None,
            run_id="run-1",
            harvested_at="2024-01-01T00:00:00Z",
            yield_grams=120.0,
            area_m2=2.0,
            fruit_count="not-a-number",
        )
    )
    profile.add_harvest_event(
        HarvestEvent(
            harvest_id="h2",
            profile_id="plant",
            species_id=None,
            run_id="run-2",
            harvested_at="2024-01-08T00:00:00Z",
            yield_grams=80.0,
            area_m2=1.0,
            fruit_count=None,
        )
    )

    recompute_statistics([profile])

    stat = profile.statistics[0]
    assert stat.metrics["harvest_count"] == 2
    assert stat.metrics["total_yield_grams"] == pytest.approx(200.0)
    assert stat.metrics["average_yield_grams"] == pytest.approx(100.0)

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["harvest_count"] == 2


def test_recompute_statistics_preserves_zero_fruit_count():
    profile = BioProfile(profile_id="plant", display_name="Plant")
    profile.add_harvest_event(
        HarvestEvent(
            harvest_id="h1",
            profile_id="plant",
            species_id=None,
            run_id=None,
            harvested_at="2024-03-01T00:00:00Z",
            yield_grams=42.0,
            area_m2=3.0,
            fruit_count=0,
        )
    )

    recompute_statistics([profile])

    stat = profile.statistics[0]
    assert stat.metrics["total_fruit_count"] == pytest.approx(0.0)

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["metrics"]["total_fruit_count"] == pytest.approx(0.0)
    assert snapshot.payload["yields"]["total_fruit_count"] == 0


def test_recompute_statistics_handles_invalid_numeric_values():
    profile = BioProfile(profile_id="plant", display_name="Plant")
    profile.add_harvest_event(
        HarvestEvent(
            harvest_id="h1",
            profile_id="plant",
            species_id=None,
            run_id="run-1",
            harvested_at="2024-01-01T00:00:00Z",
            yield_grams="not-a-number",
            area_m2="also-not-a-number",
        )
    )
    profile.add_harvest_event(
        HarvestEvent(
            harvest_id="h2",
            profile_id="plant",
            species_id=None,
            run_id="run-2",
            harvested_at="2024-01-08T00:00:00Z",
            yield_grams="42",
            area_m2=2.0,
        )
    )

    recompute_statistics([profile])

    stat = profile.statistics[0]
    assert stat.metrics["harvest_count"] == 2
    assert stat.metrics["total_yield_grams"] == pytest.approx(42.0)
    assert stat.metrics["average_yield_grams"] == pytest.approx(21.0)
    assert stat.metrics["total_area_m2"] == pytest.approx(2.0)
    assert stat.metrics["average_yield_density_g_m2"] == pytest.approx(21.0)
    assert stat.metrics["mean_density_g_m2"] == pytest.approx(21.0)


def test_species_runs_tracked_includes_run_history_when_missing_from_harvests():
    species = BioProfile(profile_id="species", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species",
    )

    cultivar.add_run_event(
        RunEvent(
            run_id="batch-1",
            profile_id="cultivar",
            species_id="species",
            started_at="2024-02-01T00:00:00Z",
        )
    )
    cultivar.add_harvest_event(
        HarvestEvent(
            harvest_id="h1",
            profile_id="cultivar",
            species_id="species",
            run_id=None,
            harvested_at="2024-02-10T00:00:00Z",
            yield_grams=42.0,
        )
    )

    recompute_statistics([species, cultivar])

    species_snapshot = next(
        (snap for snap in species.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert species_snapshot is not None
    assert species_snapshot.payload["runs_tracked"] == 1

    contributors = {item["profile_id"]: item for item in species_snapshot.payload["contributors"]}
    assert contributors["cultivar"]["runs_tracked"] == 1


def test_environment_statistics_from_run_history():
    species = BioProfile(profile_id="species", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species",
    )

    cultivar.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="cultivar",
            species_id="species",
            started_at="2024-01-01T00:00:00+00:00",
            ended_at="2024-01-11T00:00:00+00:00",
            environment={
                "temperature_c": 24.5,
                "humidity_percent": 60,
                "vpd_kpa": 0.8,
            },
        )
    )
    species.add_run_event(
        RunEvent(
            run_id="run-2",
            profile_id="species",
            species_id="species",
            started_at="2024-02-01T00:00:00+00:00",
            ended_at="2024-02-06T12:00:00+00:00",
            environment={"temperature_c": 22.0},
        )
    )

    recompute_statistics([species, cultivar])

    cultivar_env = next(
        (snap for snap in cultivar.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert cultivar_env is not None
    assert cultivar_env.payload["metrics"]["avg_temperature_c"] == pytest.approx(24.5)
    assert cultivar_env.payload["metrics"]["avg_humidity_percent"] == pytest.approx(60.0)
    assert cultivar_env.payload["metrics"]["avg_vpd_kpa"] == pytest.approx(0.8)
    assert cultivar_env.payload["runs_recorded"] == 1
    assert cultivar_env.payload["durations"]["total_days"] == pytest.approx(10.0)

    species_env = next(
        (snap for snap in species.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert species_env is not None
    assert species_env.payload["metrics"]["avg_temperature_c"] == pytest.approx((24.5 + 22.0) / 2, rel=1e-3)
    assert species_env.payload["runs_recorded"] == 2
    assert species_env.payload["samples"]["avg_temperature_c"] == 2
    contributors = {item["profile_id"]: item for item in species_env.payload["contributors"]}
    assert "cultivar" in contributors and "species" in contributors
    contrib = next(c for c in species_env.contributions if c.child_id == "cultivar")
    assert contrib.stats_version == "environment/v1"
    assert contrib.computed_at == species_env.computed_at
    assert all(c.computed_at == species_env.computed_at for c in species_env.contributions)


def test_event_statistics_normalises_blank_event_type():
    profile = BioProfile(profile_id="plant", display_name="Plant")
    profile.add_cultivation_event(
        CultivationEvent(
            event_id="evt-1",
            profile_id="plant",
            species_id=None,
            run_id=None,
            occurred_at="2024-03-01T00:00:00Z",
            event_type="   ",
        )
    )

    recompute_statistics([profile])

    event_snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "events/v1"),
        None,
    )
    assert event_snapshot is not None
    assert event_snapshot.payload["last_event"]["event_type"] == "note"
    assert event_snapshot.payload["event_types"][0]["event_type"] == "note"


def test_event_statistics_strips_and_deduplicates_tags():
    profile = BioProfile(profile_id="plant", display_name="Plant")
    profile.add_cultivation_event(
        CultivationEvent(
            event_id="evt-1",
            profile_id="plant",
            species_id=None,
            run_id=None,
            occurred_at="2024-03-02T00:00:00Z",
            event_type="inspection",
            tags=["  Growth  ", "", None, "\nGrowth\n"],
        )
    )
    profile.add_cultivation_event(
        CultivationEvent(
            event_id="evt-2",
            profile_id="plant",
            species_id=None,
            run_id=None,
            occurred_at="2024-03-03T00:00:00Z",
            event_type="inspection",
            tags=["Growth", "\tPruning\t"],
        )
    )

    recompute_statistics([profile])

    event_snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "events/v1"),
        None,
    )
    assert event_snapshot is not None
    top_tags = event_snapshot.payload.get("top_tags")
    assert top_tags is not None
    assert top_tags[0] == {"tag": "Growth", "count": 3}
    assert {tag["tag"] for tag in top_tags} == {"Growth", "Pruning"}
    assert all(tag["tag"] == tag["tag"].strip() for tag in top_tags)


def test_nutrient_statistics_include_zero_volume_events():
    species = BioProfile(profile_id="species", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species",
    )

    cultivar.add_nutrient_event(
        NutrientApplication(
            event_id="nutrient-1",
            profile_id="cultivar",
            species_id="species",
            run_id="run-1",
            applied_at="2024-04-01T00:00:00Z",
            product_name="Water",
            solution_volume_liters=0.0,
        )
    )

    recompute_statistics([species, cultivar])

    cultivar_snapshot = next(
        (snap for snap in cultivar.computed_stats if snap.stats_version == "nutrients/v1"),
        None,
    )
    assert cultivar_snapshot is not None
    cultivar_metrics = cultivar_snapshot.payload["metrics"]
    assert cultivar_metrics["total_events"] == pytest.approx(1.0)
    assert cultivar_metrics["total_volume_liters"] == pytest.approx(0.0)

    species_snapshot = next(
        (snap for snap in species.computed_stats if snap.stats_version == "nutrients/v1"),
        None,
    )
    assert species_snapshot is not None
    species_metrics = species_snapshot.payload["metrics"]
    assert species_metrics["total_events"] == pytest.approx(1.0)
    assert species_metrics["total_volume_liters"] == pytest.approx(0.0)

    contributors = {item["profile_id"]: item for item in species_snapshot.payload["contributors"]}
    assert contributors["cultivar"]["event_count"] == 1
    assert contributors["cultivar"]["total_volume_liters"] == pytest.approx(0.0)


def test_nutrient_snapshot_respects_computed_at_timestamp():
    event = NutrientApplication(
        event_id="nutrient-1",
        profile_id="p1",
        species_id="species",
        run_id=None,
        applied_at="2024-04-01T00:00:00+00:00",
        product_name="Supplement",
        solution_volume_liters=2.5,
    )
    computed_at = "2024-04-08T00:00:00+00:00"

    snapshot = _build_nutrient_snapshot(
        "p1",
        "cultivar",
        [event],
        computed_at=computed_at,
    )

    assert snapshot is not None
    assert snapshot.computed_at == computed_at
    metrics = snapshot.payload["metrics"]
    assert metrics["days_since_last_event"] == pytest.approx(7.0)


def test_event_snapshot_respects_computed_at_timestamp():
    event = CultivationEvent(
        event_id="evt-1",
        profile_id="p1",
        species_id="species",
        run_id=None,
        occurred_at="2024-04-01T00:00:00+00:00",
        event_type="inspection",
    )
    computed_at = "2024-04-08T00:00:00+00:00"

    snapshot = _build_event_snapshot(
        "p1",
        "cultivar",
        [event],
        computed_at=computed_at,
    )

    assert snapshot is not None
    assert snapshot.computed_at == computed_at
    metrics = snapshot.payload["metrics"]
    assert metrics["days_since_last_event"] == pytest.approx(7.0)
    assert snapshot.payload["last_event"]["days_since"] == pytest.approx(7.0)


def test_success_statistics_from_run_history():
    species = BioProfile(profile_id="species", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species",
    )

    cultivar.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="cultivar",
            species_id="species",
            started_at="2024-03-01T00:00:00Z",
            ended_at="2024-03-07T00:00:00Z",
            targets_met=18,
            targets_total=20,
            stress_events=1,
        )
    )
    cultivar.add_run_event(
        RunEvent(
            run_id="run-2",
            profile_id="cultivar",
            species_id="species",
            started_at="2024-03-10T00:00:00Z",
            ended_at="2024-03-18T00:00:00Z",
            success_rate=92.5,
            metadata={"stress_events": 2},
        )
    )
    species.add_run_event(
        RunEvent(
            run_id="species-run",
            profile_id="species",
            species_id="species",
            started_at="2024-04-01T00:00:00Z",
            ended_at="2024-04-15T00:00:00Z",
            metadata={"targets_met": 40, "targets_total": 50, "stress_events": 4},
        )
    )

    recompute_statistics([species, cultivar])

    cultivar_success = next(
        (snap for snap in cultivar.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert cultivar_success is not None
    payload = cultivar_success.payload
    assert payload["samples_recorded"] == 2
    assert payload["runs_tracked"] == 2
    assert payload["average_success_percent"] == pytest.approx(91.25)
    assert payload["weighted_success_percent"] == pytest.approx(90.0)
    assert payload["stress_events"] == 3
    assert payload["targets_met"] == pytest.approx(18.0)
    assert payload["targets_total"] == pytest.approx(20.0)
    assert payload["best_success_percent"] == pytest.approx(92.5)
    assert payload["worst_success_percent"] == pytest.approx(90.0)

    species_success = next(
        (snap for snap in species.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert species_success is not None
    species_payload = species_success.payload
    assert species_payload["samples_recorded"] == 3
    assert species_payload["runs_tracked"] == 3
    assert species_payload["average_success_percent"] == pytest.approx(87.5)
    assert species_payload["weighted_success_percent"] == pytest.approx(82.857, rel=1e-3)
    assert species_payload["stress_events"] == 7
    assert species_payload["targets_met"] == pytest.approx(58.0)
    assert species_payload["targets_total"] == pytest.approx(70.0)
    assert species_payload["best_success_percent"] == pytest.approx(92.5)
    assert species_payload["worst_success_percent"] == pytest.approx(80.0)

    contributors = {item["profile_id"]: item for item in species_payload["contributors"]}
    assert contributors["cultivar"]["samples_recorded"] == 2
    assert contributors["cultivar"]["average_success_percent"] == pytest.approx(91.25)
    assert contributors["cultivar"]["weighted_success_percent"] == pytest.approx(90.0)
    assert contributors["cultivar"]["targets_met"] == pytest.approx(18.0)
    assert contributors["cultivar"]["targets_total"] == pytest.approx(20.0)
    assert contributors["species"]["average_success_percent"] == pytest.approx(80.0)
    assert contributors["species"]["targets_met"] == pytest.approx(40.0)
    assert contributors["species"]["targets_total"] == pytest.approx(50.0)

    contribution_index = {contrib.child_id: contrib for contrib in species_success.contributions}
    assert contribution_index["cultivar"].stats_version == "success/v1"
    assert contribution_index["cultivar"].weight == pytest.approx(20 / 70, rel=1e-3)
    assert contribution_index["cultivar"].n_runs == 2


def test_success_statistics_accepts_percent_strings():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-02T00:00:00Z",
            success_rate="75%",
        )
    )
    profile.add_run_event(
        RunEvent(
            run_id="run-2",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-03T00:00:00Z",
            ended_at="2024-01-04T00:00:00Z",
            success_rate="50%",
        )
    )

    recompute_statistics([profile])

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["average_success_percent"] == pytest.approx(62.5)
    assert snapshot.payload["weighted_success_percent"] == pytest.approx(62.5)


def test_success_statistics_deduplicates_run_ids():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id=" run-1 ",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-02T00:00:00Z",
            success_rate=0.9,
        )
    )
    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-03T00:00:00Z",
            ended_at="2024-01-04T00:00:00Z",
            success_rate=0.8,
        )
    )

    recompute_statistics([profile])

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["runs_tracked"] == 1


def test_success_statistics_handles_fractional_percent_strings():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-01T00:00:00Z",
            ended_at="2024-01-02T00:00:00Z",
            success_rate="0.5%",
        )
    )
    profile.add_run_event(
        RunEvent(
            run_id="run-2",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-03T00:00:00Z",
            ended_at="2024-01-04T00:00:00Z",
            success_rate="1%",
        )
    )

    recompute_statistics([profile])

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["average_success_percent"] == pytest.approx(0.75)
    assert snapshot.payload["weighted_success_percent"] == pytest.approx(0.75)


def test_success_statistics_handles_fraction_notation_strings():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-05T00:00:00Z",
            ended_at="2024-01-06T00:00:00Z",
            success_rate="5/10",
        )
    )
    profile.add_run_event(
        RunEvent(
            run_id="run-2",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-07T00:00:00Z",
            ended_at="2024-01-08T00:00:00Z",
            success_rate="3/6",
        )
    )

    recompute_statistics([profile])

    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "success/v1"),
        None,
    )
    assert snapshot is not None
    assert snapshot.payload["average_success_percent"] == pytest.approx(50.0)
    assert snapshot.payload["weighted_success_percent"] == pytest.approx(50.0)


def test_success_statistics_handles_non_finite_fraction_parts():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-01-09T00:00:00Z",
            ended_at="2024-01-10T00:00:00Z",
            success_rate="1e309/2",
        )
    )

    recompute_statistics([profile])

    assert all(snap.stats_version != "success/v1" for snap in profile.computed_stats)


def test_success_statistics_ignore_nan_success_rates():
    profile = BioProfile(profile_id="p1", display_name="Plant")

    profile.add_run_event(
        RunEvent(
            run_id="run-1",
            profile_id="p1",
            species_id=None,
            started_at="2024-05-01T00:00:00Z",
            success_rate=float("nan"),
        )
    )

    recompute_statistics([profile])

    assert all(snap.stats_version != "success/v1" for snap in profile.computed_stats)
