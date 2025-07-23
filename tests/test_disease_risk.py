from plant_engine import disease_monitor


def test_estimate_disease_risk_high():
    env = {"temperature": 22, "humidity": 75}
    risk = disease_monitor.estimate_disease_risk("citrus", env)
    assert risk["citrus_greening"] == "high"
    assert risk["root_rot"] == "high"


def test_estimate_disease_risk_moderate():
    env = {"temperature": 18, "humidity": 50}
    risk = disease_monitor.estimate_disease_risk("citrus", env)
    assert risk["citrus_greening"] == "moderate"
    assert risk["root_rot"] == "moderate"
