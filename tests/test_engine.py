import json

from plant_engine import engine
from plant_engine import growth_model


def test_run_daily_cycle_with_rootzone(tmp_path, monkeypatch):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    output_dir = tmp_path / "reports"
    growth_dir = tmp_path / "growth"

    # Patch directories used by engine and growth_model
    monkeypatch.setattr(engine, "PLANTS_DIR", str(plants_dir))
    monkeypatch.setattr(engine, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(growth_model, "GROWTH_DIR", str(growth_dir))

    plant_path = plants_dir / "sample.json"
    plant_path.write_text(
        json.dumps(
            {
                "plant_type": "citrus",
                "stage": "seedling",
                "kc": 1.0,
                "canopy_m2": 0.5,
                "max_root_depth_cm": 30,
                "last_irrigation_ml": 800,
                "thresholds": {"soil_moisture_pct": 30},
                "latest_env": {
                    "temp_c": 24,
                    "temp_c_max": 26,
                    "temp_c_min": 20,
                    "rh_pct": 60,
                    "par_w_m2": 300,
                },
                "observed_pests": ["aphids"],
                "observed_diseases": ["root rot"],
            }
        )
    )

    report = engine.run_daily_cycle("sample")

    assert "rootzone" in report
    assert report["rootzone"]["mad_pct"] == 0.5
    assert "stage_info" in report
    assert report["pest_actions"]["aphids"].startswith("Apply insecticidal")
    assert report["disease_actions"]["root rot"].startswith("Ensure good drainage")
    assert (output_dir / "sample.json").exists()

    assert "environment_optimization" in report
    assert report["environment_optimization"]["setpoints"]["temp_c"] == 24
    assert "nutrient_targets" in report


def test_load_profile(tmp_path, monkeypatch):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    monkeypatch.setattr(engine, "PLANTS_DIR", str(plants_dir))
    path = plants_dir / "demo.json"
    path.write_text('{"a":1}')
    data = engine.load_profile("demo")
    assert data["a"] == 1


def test_daily_report_as_dict():
    from plant_engine.report import DailyReport

    report = DailyReport(
        plant_id="x",
        thresholds={},
        growth={},
        transpiration={},
        water_deficit={},
        rootzone={},
        nue={},
        guidelines={},
        nutrient_targets={},
        environment_actions={},
        environment_optimization={},
        pest_actions={},
        disease_actions={},
        lifecycle_stage="seedling",
        stage_info={},
        tags=[],
    )

    d = report.as_dict()
    assert d["plant_id"] == "x"
    assert d["lifecycle_stage"] == "seedling"

