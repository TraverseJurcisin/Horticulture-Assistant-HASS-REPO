from datetime import datetime, timedelta
import pytest

from custom_components.horticulture_assistant.utils.nutrient_tracker import (
    NutrientTracker,
    NutrientDeliveryRecord,
    register_fertilizers_from_dataset,
)


def test_summarize_mg_for_period():
    tracker = NutrientTracker()
    now = datetime.now()
    tracker.delivery_log.extend([
        NutrientDeliveryRecord("pid", "b1", now - timedelta(days=2), {"N": 10}, 1.0),
        NutrientDeliveryRecord("pid", "b2", now - timedelta(days=1), {"N": 20}, 0.5),
        NutrientDeliveryRecord("pid", "b3", now, {"N": 30}, 1.0),
    ])
    start = now - timedelta(days=1)
    end = now
    summary = tracker.summarize_mg_for_period(start, end, "pid")
    assert summary["N"] == 40.0


def test_summarize_mg_for_period_invalid_range():
    tracker = NutrientTracker()
    now = datetime.now()
    with pytest.raises(ValueError):
        tracker.summarize_mg_for_period(now, now - timedelta(days=1))


def test_summarize_mg_since():
    tracker = NutrientTracker()
    now = datetime.now()
    tracker.delivery_log.extend(
        [
            NutrientDeliveryRecord("p", "b1", now - timedelta(days=3), {"N": 10}, 1.0),
            NutrientDeliveryRecord("p", "b2", now - timedelta(days=1), {"N": 20}, 1.0),
            NutrientDeliveryRecord("p", "b3", now, {"N": 30}, 1.0),
        ]
    )

    summary = tracker.summarize_mg_since(2, "p", now=now)
    assert summary["N"] == 50.0

    with pytest.raises(ValueError):
        tracker.summarize_mg_since(-1)


def test_summarize_daily_totals_and_dataset_registration():
    tracker = NutrientTracker()
    register_fertilizers_from_dataset(tracker)
    assert "foxfarm_grow_big" in tracker.product_profiles

    profile = tracker.product_profiles["foxfarm_grow_big"]
    n_entry = profile.nutrient_map.get("N")
    assert n_entry and n_entry.value_mg_per_kg == pytest.approx(60000, abs=1)

    now = datetime.now()
    tracker.delivery_log.append(
        NutrientDeliveryRecord("p", "b1", now, {"N": 100}, 2.0)
    )
    totals = tracker.summarize_daily_totals("p")
    today = now.date().isoformat()
    assert totals[today]["N"] == 200.0
