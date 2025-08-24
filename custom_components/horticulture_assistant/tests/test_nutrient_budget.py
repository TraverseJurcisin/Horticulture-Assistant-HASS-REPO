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


def test_estimate_fertilizer_requirements():
    ferts = {"N": "urea", "P": "map", "K": "kcl"}
    masses = nutrient_budget.estimate_fertilizer_requirements("lettuce", 1.0, ferts, efficiency=1.0)
    assert round(masses["urea"], 2) == round(1.2 / 0.46, 2)
    assert round(masses["map"], 2) == round(0.2 / 0.22, 2)
    assert round(masses["kcl"], 2) == round(1.5 / 0.5, 2)


def test_estimate_solution_volume():
    masses = {"foxfarm_grow_big": 150, "magriculture": 800}
    volumes = nutrient_budget.estimate_solution_volume(masses)
    assert volumes["foxfarm_grow_big"] == 0.5  # 150g / 300 g/L
    assert volumes["magriculture"] == 1.0  # 800g / 800 g/L


def test_estimate_fertilizer_cost():
    ferts = {"N": "foxfarm_grow_big", "P": "foxfarm_grow_big", "K": "foxfarm_grow_big"}
    cost = nutrient_budget.estimate_fertilizer_cost("lettuce", 1.0, ferts, efficiency=1.0)
    assert cost > 0
