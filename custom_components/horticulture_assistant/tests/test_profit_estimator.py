import importlib

from plant_engine import profit_estimator, utils, yield_manager


def test_get_crop_price():
    assert profit_estimator.get_crop_price("lettuce") == 3.0
    assert profit_estimator.get_crop_price("unknown") is None


def test_estimate_profit(tmp_path):
    plant_id = "profitplant"
    yield_manager.YIELD_DIR = str(tmp_path)
    yield_manager.record_harvest(plant_id, grams=1000)
    profit = profit_estimator.estimate_profit(plant_id, "lettuce", {"water": 0.5, "fertilizer": 0.3})
    # revenue = 1kg * $3 = 3.0, cost=0.8, profit=2.2
    assert profit == 2.2


def test_estimate_expected_profit(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "economics").mkdir()
    (data_dir / "yield").mkdir()
    (data_dir / "economics" / "crop_market_prices.json").write_text('{"lettuce": 3}')
    (data_dir / "economics" / "crop_production_costs.json").write_text('{"lettuce": 1}')
    (data_dir / "yield" / "yield_estimates.json").write_text('{"lettuce": 1000}')

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))

    utils.clear_dataset_cache()

    importlib.reload(yield_manager)
    importlib.reload(profit_estimator)

    profit = profit_estimator.estimate_expected_profit("lettuce")
    # revenue = 1kg * $3 = 3, cost = 1kg * $1 = 1, profit = 2
    assert profit == 2.0

    # clear modified dataset state
    monkeypatch.delenv("HORTICULTURE_DATA_DIR", raising=False)
    utils.clear_dataset_cache()
    importlib.reload(yield_manager)
    importlib.reload(profit_estimator)
