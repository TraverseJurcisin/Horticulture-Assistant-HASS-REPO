import json

from ..engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_infiltration(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    profile = {
        "general": {
            "plant_type": "lettuce",
            "lifecycle_stage": "vegetative",
            "soil_texture": "loam",
            "surface_area_m2": 0.1,
        }
    }
    (plants_dir / "plant1.json").write_text(json.dumps(profile))
    (plants_dir / "plant1").mkdir()

    report = run_daily_cycle("plant1", base_path=str(plants_dir), output_path=str(out_dir))

    infil = report["root_zone"].get("infiltration_time_hr")
    assert infil == 0.15
