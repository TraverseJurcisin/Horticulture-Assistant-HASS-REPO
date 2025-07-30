import json
from custom_components.horticulture_assistant.engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_monitor_date(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    profile = {"general": {"plant_type": "tomato", "lifecycle_stage": "fruiting"}}
    (plants_dir / "p.json").write_text(json.dumps(profile))
    plant_dir = plants_dir / "p"
    plant_dir.mkdir()
    log = [{"timestamp": "2023-01-01T00:00:00+00:00"}]
    (plant_dir / "pest_scouting_log.json").write_text(json.dumps(log))

    report = run_daily_cycle("p", base_path=str(plants_dir), output_path=str(out_dir))
    assert report["next_pest_monitor_date"] == "2023-01-04"
