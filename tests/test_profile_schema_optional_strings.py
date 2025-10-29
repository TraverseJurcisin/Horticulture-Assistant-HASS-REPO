from custom_components.horticulture_assistant.profile.schema import (
    CultivationEvent,
    HarvestEvent,
    NutrientApplication,
    RunEvent,
)


def test_profile_events_preserve_zero_identifiers() -> None:
    run = RunEvent.from_json(
        {
            "run_id": 0,
            "profile_id": 0,
            "species_id": 0,
            "started_at": "2024-01-01T00:00:00Z",
        }
    )

    assert run.run_id == "0"
    assert run.profile_id == "0"
    assert run.species_id == "0"

    cultivation = CultivationEvent.from_json(
        {
            "event_id": 1,
            "profile_id": 2,
            "occurred_at": "2024-01-01T00:00:00Z",
            "event_type": "note",
            "run_id": 0,
            "species_id": 0,
            "title": 0,
        }
    )

    assert cultivation.run_id == "0"
    assert cultivation.species_id == "0"
    assert cultivation.title == "0"

    harvest = HarvestEvent.from_json(
        {
            "harvest_id": 3,
            "profile_id": 4,
            "harvested_at": "2024-01-02T00:00:00Z",
            "yield_grams": 10,
            "run_id": 0,
            "species_id": 0,
        }
    )

    assert harvest.run_id == "0"
    assert harvest.species_id == "0"

    nutrient = NutrientApplication.from_json(
        {
            "event_id": 5,
            "profile_id": 6,
            "applied_at": "2024-01-03T00:00:00Z",
            "run_id": 0,
            "species_id": 0,
            "product_id": 0,
        }
    )

    assert nutrient.run_id == "0"
    assert nutrient.species_id == "0"
    assert nutrient.product_id == "0"
    assert nutrient.summary()["run_id"] == "0"


def test_run_event_rejects_boolean_metrics() -> None:
    event = RunEvent.from_json(
        {
            "run_id": "example",
            "profile_id": "plant",
            "started_at": "2024-01-01T00:00:00Z",
            "targets_met": True,
            "targets_total": False,
            "success_rate": True,
            "stress_events": False,
        }
    )

    assert event.targets_met is None
    assert event.targets_total is None
    assert event.success_rate is None
    assert event.stress_events is None
