import pytest

from plant_engine.nutrient_planner import (
    NutrientManagementCostReport,
    NutrientManagementReport,
    generate_nutrient_management_report,
    generate_nutrient_management_report_with_cost,
)


def test_generate_nutrient_management_report():
    current = {"N": 50, "P": 10, "K": 40}
    report = generate_nutrient_management_report(
        current,
        "lettuce",
        "seedling",
        volume_l=5.0,
        purity={"N": 0.2, "P": 0.2, "K": 0.2},
    )
    assert isinstance(report, NutrientManagementReport)
    assert report.analysis.recommended["N"] == 80
    assert report.corrections_g["N"] > 0
    assert report.analysis.deficiencies


def test_generate_nutrient_management_report_invalid_volume():
    with pytest.raises(ValueError):
        generate_nutrient_management_report(
            {"N": 50},
            "lettuce",
            "seedling",
            volume_l=0,
        )


def test_generate_nutrient_management_report_with_cost():
    current = {"N": 50, "P": 10, "K": 40}
    report = generate_nutrient_management_report_with_cost(
        current,
        "lettuce",
        "seedling",
        volume_l=5.0,
    )
    assert isinstance(report, NutrientManagementCostReport)
    assert report.cost_total >= 0
