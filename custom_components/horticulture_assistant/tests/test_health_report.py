from plant_engine.health_report import generate_health_report


def test_generate_health_report():
    env = {"temp_c": 18, "humidity_pct": 90}
    nutrients = {"N": 50, "K": 70}
    report = generate_health_report(
        "citrus",
        "vegetative",
        env,
        nutrients,
        pests=["aphids"],
        diseases=["root rot"],
    )
    assert "environment" in report
    assert report["deficiencies"]
    assert report["deficiency_treatments"]
    assert report["pest_actions"]["aphids"].startswith("Apply")
    assert report["disease_actions"]["root rot"].startswith("Ensure")
    assert isinstance(report["stage_tasks"], list)


def test_generate_health_report_with_water():
    env = {"temp_c": 22, "humidity_pct": 70}
    nutrients = {"N": 50, "K": 70}
    report = generate_health_report(
        "citrus",
        "vegetative",
        env,
        nutrients,
        water_test={"Na": 60},
    )
    assert report["environment"]["water_quality"]["rating"] == "fair"

