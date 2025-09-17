import json
from datetime import datetime, timezone

from custom_components.horticulture_assistant.engine.run_daily_cycle import run_daily_cycle

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

def test_run_daily_cycle_nutrient_analysis(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    (plants_dir / "plant1.json").write_text(
        json.dumps({"general": {"plant_type": "citrus", "lifecycle_stage": "vegetative"}})
    )
    plant_dir = plants_dir / "plant1"
    plant_dir.mkdir()
    log = [
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "nutrient_formulation": {"N": 50, "P": 20, "K": 40},
        }
    ]
    (plant_dir / "nutrient_application_log.json").write_text(json.dumps(log))

    report = run_daily_cycle("plant1", base_path=str(plants_dir), output_path=str(out_dir))

    assert "nutrient_analysis" in report
    assert report["nutrient_analysis"]["recommended"]["N"] == 80
    # verify nutrient deficiency detection
    assert "deficiency_actions" in report
    assert report["deficiency_actions"]["Ca"]["severity"] == "severe"
    # new expected uptake reporting
    assert report["expected_uptake"]["N"] == 50
    assert report["uptake_gap"]["K"] == 20
    assert isinstance(report["stage_deficit"], dict)
    assert "environment_score" in report
    assert "environment_quality" in report
