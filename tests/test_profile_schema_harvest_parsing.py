import pytest

from custom_components.horticulture_assistant.profile.schema import HarvestEvent


def test_harvest_event_from_json_parses_numeric_strings() -> None:
    harvest = HarvestEvent.from_json(
        {
            "harvest_id": "h1",
            "profile_id": "p1",
            "harvested_at": "2024-01-01T00:00:00Z",
            "yield_grams": "1,234.5 g",
            "area_m2": "2.5 m²",
            "wet_weight_grams": "1,500g",
            "dry_weight_grams": "750 grams",
            "fruit_count": "12 fruits",
        }
    )

    assert harvest.yield_grams == pytest.approx(1234.5)
    assert harvest.area_m2 == pytest.approx(2.5)
    assert harvest.wet_weight_grams == pytest.approx(1500.0)
    assert harvest.dry_weight_grams == pytest.approx(750.0)
    assert harvest.fruit_count == 12


def test_harvest_event_from_json_parses_localized_numeric_strings() -> None:
    harvest = HarvestEvent.from_json(
        {
            "harvest_id": "h-eu",
            "profile_id": "p-eu",
            "harvested_at": "2024-01-03T00:00:00Z",
            "yield_grams": "1.234,5 g",
            "area_m2": "1 234,5 m²",
            "wet_weight_grams": "1 500,0 g",
            "dry_weight_grams": "750,0 g",
            "fruit_count": "1 200 berries",
        }
    )

    assert harvest.yield_grams == pytest.approx(1234.5)
    assert harvest.area_m2 == pytest.approx(1234.5)
    assert harvest.wet_weight_grams == pytest.approx(1500.0)
    assert harvest.dry_weight_grams == pytest.approx(750.0)
    assert harvest.fruit_count == 1200


def test_harvest_event_from_json_parses_thousands_with_commas() -> None:
    harvest = HarvestEvent.from_json(
        {
            "harvest_id": "h-comma",
            "profile_id": "p-comma",
            "harvested_at": "2024-01-04T00:00:00Z",
            "yield_grams": "1,234",
            "area_m2": "3,456",
        }
    )

    assert harvest.yield_grams == pytest.approx(1234.0)
    assert harvest.area_m2 == pytest.approx(3456.0)


def test_harvest_event_from_json_handles_missing_numeric_data() -> None:
    harvest = HarvestEvent.from_json(
        {
            "harvest_id": "h2",
            "profile_id": "p2",
            "harvested_at": "2024-01-02T00:00:00Z",
            "yield_grams": "not available",
            "area_m2": "unknown",
            "wet_weight_grams": None,
            "dry_weight_grams": "",
            "fruit_count": "n/a",
        }
    )

    assert harvest.yield_grams == 0.0
    assert harvest.area_m2 is None
    assert harvest.wet_weight_grams is None
    assert harvest.dry_weight_grams is None
    assert harvest.fruit_count is None
