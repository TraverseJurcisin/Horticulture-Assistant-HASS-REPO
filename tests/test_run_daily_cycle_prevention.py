import json
from custom_components.horticulture_assistant.engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_prevention(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    profile = {
        "general": {
            "plant_type": "citrus",
            "lifecycle_stage": "vegetative",
            "observed_pests": ["aphids"],
            "observed_diseases": ["root rot"],
        }
    }
    (plants_dir / "c.json").write_text(json.dumps(profile))

    report = run_daily_cycle("c", base_path=str(plants_dir), output_path=str(out_dir))

    assert report["pest_prevention"]["aphids"].startswith("Encourage")
    assert report["disease_prevention"]["root rot"].startswith("Plant in well-drained")
