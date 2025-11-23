from ..engine.plant_engine.health_management import generate_management_plan


def test_generate_management_plan():
    plan = generate_management_plan(
        "citrus",
        pests=["aphids"],
        diseases=["root rot"],
        pest_severity={"aphids": "moderate"},
        disease_severity={"root rot": "severe"},
    )
    assert "pest_management" in plan
    assert "disease_management" in plan
    assert plan["pest_management"]["aphids"]["severity_action"].startswith("Deploy")
    assert plan["disease_management"]["root rot"]["severity_action"].startswith("Implement")
