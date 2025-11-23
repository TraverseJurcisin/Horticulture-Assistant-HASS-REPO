import json

from ..engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_stage_tasks(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    (plants_dir / "plant1.json").write_text(
        json.dumps({"general": {"plant_type": "tomato", "lifecycle_stage": "vegetative"}})
    )
    plant_dir = plants_dir / "plant1"
    plant_dir.mkdir()

    report = run_daily_cycle("plant1", base_path=str(plants_dir), output_path=str(out_dir))

    assert report["stage_tasks"] == ["Prune side shoots", "Apply balanced fertilizer"]
    assert "environment_score" in report
    assert "environment_quality" in report
