from plant_engine import nutrient_budget


def test_get_removal_rates():
    rates = nutrient_budget.get_removal_rates("lettuce")
    assert rates["N"] == 1.2
    assert rates["P"] == 0.2
    assert rates["K"] == 1.5


def test_estimate_total_removal():
    est = nutrient_budget.estimate_total_removal("tomato", 2.0)
    data = est.as_dict()["nutrients_g"]
    assert data["N"] == 6.2
    assert data["P"] == 0.8
    assert data["K"] == 7.0


def test_estimate_required_nutrients():
    est = nutrient_budget.estimate_required_nutrients("strawberry", 1.0, efficiency=0.8)
    data = est.as_dict()["nutrients_g"]
    assert data["N"] == 2.25  # 1.8 / 0.8
    assert data["P"] == 0.37  # 0.3 / 0.8 -> ~0.375
    assert data["K"] == 2.5

