from datetime import datetime

from ..utils.cost_analyzer import CostAnalyzer, ProductPriceEntry


def test_cost_analyzer_basic():
    entry = ProductPriceEntry(
        product_id="foo",
        distributor="A",
        package_size_unit="L",
        package_size=1.0,
        price=10.0,
        date_purchased=datetime(2024, 1, 1),
    )
    analyzer = CostAnalyzer()
    analyzer.add_price_entry(entry)
    assert analyzer.get_latest_price_per_unit("foo") == 10.0
    summary = analyzer.summarize_costs()
    assert summary["foo"] == 10.0
    assert analyzer.get_latest_price_per_unit("missing") is None
