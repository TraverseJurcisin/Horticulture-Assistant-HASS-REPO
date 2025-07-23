import importlib
from custom_components.horticulture_assistant.utils import fertilizer_cost_analyzer as fca


def test_price_per_unit():
    assert fca.price_per_unit(10, 1, "kg") == 10
    assert round(fca.price_per_unit(5, 500, "g"), 2) == 10


def test_get_cheapest_option():
    opts = [
        fca.ProductOption(price=10, quantity=1, unit="kg", supplier="A"),
        fca.ProductOption(price=8, quantity=500, unit="g", supplier="B"),
    ]
    best = fca.get_cheapest_option(opts)
    assert best and best.supplier == "A"


def test_compare_ingredient_costs():
    opts = [
        fca.ProductOption(
            price=10,
            quantity=1,
            unit="kg",
            supplier="A",
            ingredients={"N": 1000},
        ),
        fca.ProductOption(
            price=12,
            quantity=2,
            unit="kg",
            supplier="B",
            ingredients={"N": 3000},
        ),
    ]
    costs = fca.compare_ingredient_costs(opts)
    assert "N" in costs
    assert round(costs["N"], 3) == 0.004
