from plant_engine.nutrient_planner import (
    generate_nutrient_management_report,
    NutrientManagementReport,
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
    assert report.analysis["recommended"]["N"] == 80
    assert report.corrections_g["N"] > 0
    assert "deficiencies" in report.analysis
