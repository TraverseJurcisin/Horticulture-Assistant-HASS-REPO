import datetime
import json

from ..engine.run_daily_cycle import run_daily_cycle


def test_run_daily_cycle_extended(tmp_path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    out_dir = tmp_path / "reports"

    plant_path = plants_dir / "sample.json"
    plant_path.write_text(
        json.dumps(
            {
                "general": {
                    "plant_type": "tomato",
                    "lifecycle_stage": "vegetative",
                    "start_date": "2025-01-01",
                    "observed_pests": ["aphids"],
                    "observed_diseases": [],
                    "observed_pest_counts": {"aphids": 12},
                }
            }
        )
    )

    (plants_dir / "sample").mkdir()
    (plants_dir / "sample" / "water_quality_log.json").write_text(
        json.dumps(
            [
                {
                    "results": {"Na": 60, "Cl": 50},
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                }
            ]
        )
    )

    report = run_daily_cycle("sample", base_path=str(plants_dir), output_path=str(out_dir))

    assert report["beneficial_insects"]["aphids"][0] == "ladybugs"
    assert report["pest_severity"]["aphids"] == "moderate"
    assert report["predicted_harvest_date"] == "2025-05-01"
    assert report["stage_progress_pct"] is not None
    assert "environment_optimization" in report
    assert "environment_score" in report
    assert "environment_quality" in report
    assert "fertigation_schedule" in report
    assert "fertigation_cost" in report
    assert (out_dir / f"sample_{report['timestamp'][:10]}.json").exists()
    assert report["water_quality_summary"]["rating"] == "fair"
