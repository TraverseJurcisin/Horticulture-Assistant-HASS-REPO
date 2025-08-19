import json
from pathlib import Path

from ruamel.yaml import YAML

from scripts.generate_plant_sensors import generate_template_yaml, generate_from_directory


def _sample_report():
    return {
        "growth": {"vgi_today": 2, "vgi_total": 20},
        "transpiration": {"transpiration_ml_day": 150},
        "water_deficit": {"ml_available": 500, "depletion_pct": 0.25, "mad_crossed": False},
        "nue": {"nue": {"N": 1.5}},
        "thresholds": {"N": 100}
    }


def test_generate_template_yaml(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    report_file = report_dir / "plant1.json"
    report_file.write_text(json.dumps(_sample_report()))
    out_dir = tmp_path / "out"

    out_path = generate_template_yaml("plant1", report_dir, out_dir)
    assert out_path.exists()

    yaml = YAML(typ="safe")
    data = yaml.load(out_path.read_text())
    sensors = data["template"][0]["sensor"]
    names = {s["name"] for s in sensors}
    assert "plant1 VGI Today" in names
    assert "plant1 NUE N" in names


def test_generate_from_directory(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    for pid in ["one", "two"]:
        (report_dir / f"{pid}.json").write_text(json.dumps(_sample_report()))
    out_dir = tmp_path / "out"

    paths = generate_from_directory(report_dir, out_dir)
    assert len(paths) == 2
    assert sorted(p.stem for p in paths) == ["one_sensors", "two_sensors"]
