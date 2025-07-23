from datetime import datetime, timedelta
import pytest

from custom_components.horticulture_assistant.utils.nutrient_tracker import (
    NutrientTracker,
    NutrientDeliveryRecord,
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
