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
    assert report["pest_actions"]["aphids"].startswith("Apply")
    assert report["disease_actions"]["root rot"].startswith("Ensure")

