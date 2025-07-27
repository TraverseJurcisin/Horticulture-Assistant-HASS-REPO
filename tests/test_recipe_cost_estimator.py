from custom_components.horticulture_assistant.utils.recipe_cost_estimator import estimate_recipe_cost
import pytest


def test_estimate_recipe_cost_basic():
    rates = {"p1": 2.0, "p2": 1.0}
    costs = {"p1": 0.5, "p2": 1.0}
    result = estimate_recipe_cost(rates, costs, 10)
    assert result["total_cost"] == pytest.approx(20.0)
    assert result["product_costs"]["p1"] == pytest.approx(10.0)
    assert result["product_costs"]["p2"] == pytest.approx(10.0)


def test_estimate_recipe_cost_invalid_volume():
    with pytest.raises(ValueError):
        estimate_recipe_cost({"p1": 1.0}, {"p1": 1.0}, 0)
