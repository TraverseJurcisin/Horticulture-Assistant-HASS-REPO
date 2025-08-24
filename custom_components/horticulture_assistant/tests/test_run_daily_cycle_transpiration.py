import json

from custom_components.horticulture_assistant.engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_transpiration(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    env = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400, "wind_speed_m_s": 1.0, "elevation_m": 200}
    profile = {
        "general": {
            "plant_type": "lettuce",
            "lifecycle_stage": "vegetative",
            "latest_env": env,
            "canopy_m2": 0.25,
        }
    }
    (plants_dir / "plant1.json").write_text(json.dumps(profile))
    plant_dir = plants_dir / "plant1"
    plant_dir.mkdir()

    report = run_daily_cycle("plant1", base_path=str(plants_dir), output_path=str(out_dir))

    assert "transpiration" in report
    assert report["transpiration"]["transpiration_ml_day"] > 0
    assert "environment_score" in report
    assert "environment_quality" in report
