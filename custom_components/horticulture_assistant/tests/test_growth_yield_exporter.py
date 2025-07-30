import json
from pathlib import Path

from custom_components.horticulture_assistant.analytics import growth_yield_exporter as gy


def test_export_growth_yield(tmp_path, monkeypatch):
    plants_dir = tmp_path / "plants"
    plant_dir = plants_dir / "plant1"
    plant_dir.mkdir(parents=True)
    yield_log = plant_dir / "yield_tracking_log.json"
    yield_log.write_text(json.dumps([{"timestamp": "2025-01-01", "yield_quantity": 5}]))

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    trends = {"plant1": {"2025-01-01": {"vgi": 1.2}}}
    (data_dir / "growth_trends.json").write_text(json.dumps(trends))
    monkeypatch.setattr(gy, "data_path", lambda hass, *parts: str(data_dir / parts[0]))

    out_dir = tmp_path / "out"
    series = gy.export_growth_yield(
        "plant1",
        base_path=str(plants_dir),
        output_path=str(out_dir),
        force=True,
    )

    assert series[0]["yield_quantity"] == 5
    assert series[0]["growth_metric"] == 1.2
    assert (out_dir / "plant1_growth_yield.json").is_file()
