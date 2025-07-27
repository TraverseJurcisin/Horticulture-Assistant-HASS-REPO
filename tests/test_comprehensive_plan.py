from datetime import date

from scripts import comprehensive_plan


def test_generate_plan():
    plan = comprehensive_plan.generate_plan(
        "lettuce",
        "vegetative",
        3,
        date(2025, 1, 1),
        2,
    )
    assert "environment" in plan
    assert "fertigation_schedule" in plan
    assert "monitoring_schedule" in plan
    assert len(plan["fertigation_schedule"]) == 3
    assert len(plan["monitoring_schedule"]) == 2
