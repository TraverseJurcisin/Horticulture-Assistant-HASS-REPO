import pytest

from ..utils.product_cost_analyzer import ProductCostAnalyzer


def test_cost_per_unit_basic():
    assert ProductCostAnalyzer.cost_per_unit(10.0, 1.0, "L") == 10.0
    assert ProductCostAnalyzer.cost_per_unit(10.0, 1000.0, "mL") == 10.0
    assert ProductCostAnalyzer.cost_per_unit(5.0, 1.0, "kg") == 5.0
    with pytest.raises(ValueError):
        ProductCostAnalyzer.cost_per_unit(1.0, 0.0, "L")
    with pytest.raises(ValueError):
        ProductCostAnalyzer.cost_per_unit(1.0, 1.0, "unknown")


def test_compare_sources():
    data = [
        {"price": 10.0, "size": 1.0, "unit": "L"},
        {"price": 5.0, "size": 500.0, "unit": "mL"},
    ]
    result = ProductCostAnalyzer.compare_sources(data)
    assert result == {
        "min_cost_per_unit": 10.0,
        "max_cost_per_unit": 10.0,
        "avg_cost_per_unit": 10.0,
    }
    with pytest.raises(ValueError):
        ProductCostAnalyzer.compare_sources([])


def test_cost_of_dose():
    per_unit = ProductCostAnalyzer.cost_per_unit(10.0, 1.0, "L")
    assert ProductCostAnalyzer.cost_of_dose(per_unit, 100.0, "mL") == 1.0
    with pytest.raises(ValueError):
        ProductCostAnalyzer.cost_of_dose(per_unit, 1.0, "bad")
