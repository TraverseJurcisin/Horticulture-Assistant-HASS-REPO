import importlib
import json


def _import_cycle():
    module = importlib.import_module(
        "custom_components.horticulture_assistant.engine.run_daily_cycle"
    )
    importlib.reload(module)
    return module.run_daily_cycle


def test_run_daily_cycle_remaining_yield(tmp_path, monkeypatch):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    (plants_dir / "p.json").write_text(
        json.dumps({"general": {"plant_type": "tomato", "lifecycle_stage": "vegetative"}})
    )
    (plants_dir / "p").mkdir()

    yield_dir = tmp_path / "yield"
    yield_dir.mkdir()
    (yield_dir / "p.json").write_text(
        json.dumps({"harvests": [{"date": "2024-01-01", "yield_grams": 300}]})
    )

    monkeypatch.setenv("HORTICULTURE_YIELD_DIR", str(yield_dir))
    import plant_engine.yield_manager as ym
    import plant_engine.yield_prediction as yp

    importlib.reload(ym)
    importlib.reload(yp)
    run_daily_cycle = _import_cycle()
    report = run_daily_cycle("p", base_path=str(plants_dir), output_path=str(out_dir))

    assert report["remaining_yield_g"] == 3200.0
    # Reset cached datasets for subsequent tests
    import plant_engine.utils as utils

    importlib.reload(utils)
