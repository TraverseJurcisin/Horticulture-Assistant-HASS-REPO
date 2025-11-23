from ..engine.plant_engine import pest_monitor


def test_estimate_pest_risk_high():
    env = {"temperature": 26, "humidity": 80}
    risk = pest_monitor.estimate_pest_risk("citrus", env)
    assert risk["aphids"] == "high"
    assert risk["mites"] == "moderate"


def test_estimate_pest_risk_moderate():
    env = {"temperature": 22, "humidity": 40}
    risk = pest_monitor.estimate_pest_risk("citrus", env)
    assert risk["mites"] == "high"
    assert risk["aphids"] == "moderate"


def test_adjust_risk_with_resistance():
    risk = {"whiteflies": "high"}
    adjusted = pest_monitor.adjust_risk_with_resistance("tomato", risk)
    assert adjusted["whiteflies"] == "moderate"


def test_estimate_adjusted_pest_risk():
    env = {"temperature": 25, "humidity": 80}
    risk = pest_monitor.estimate_adjusted_pest_risk("tomato", env)
    assert risk["whiteflies"] == "moderate"
