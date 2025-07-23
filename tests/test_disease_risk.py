from plant_engine import disease_monitor


def test_estimate_disease_risk_high():
    env = {"temperature": 25, "humidity": 90}
    risk = disease_monitor.estimate_disease_risk("citrus", env)
    assert risk["greasy_spot"] == "high"
    assert risk["powdery_mildew"] == "high"


def test_estimate_disease_risk_moderate():
    env = {"temperature": 17, "humidity": 75}
    risk = disease_monitor.estimate_disease_risk("tomato", env)
    assert risk["blight"] == "moderate"
