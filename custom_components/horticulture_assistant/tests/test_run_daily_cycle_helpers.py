import pytest

from custom_components.horticulture_assistant.engine.run_daily_cycle import (
    _summarize_irrigation,
    _aggregate_nutrients,
    _average_sensor_data,
    _compute_expected_uptake,
    _load_logs,
    _build_root_zone_info,
)


def test_summarize_irrigation():
    entries = [
        {"volume_applied_ml": 100, "method": "drip"},
        {"volume_applied_ml": 150, "method": "drip"},
    ]
    summary = _summarize_irrigation(entries)
    assert summary["events"] == 2
    assert summary["total_volume_ml"] == 250
    assert summary["methods"] == ["drip"]


def test_aggregate_nutrients():
    entries = [
        {"nutrient_formulation": {"N": 50, "K": 20}},
        {"nutrient_formulation": {"N": 25, "P": 10}},
    ]
    totals = _aggregate_nutrients(entries)
    assert totals == {"N": 75, "K": 20, "P": 10}


def test_average_sensor_data():
    entries = [
        {"sensor_type": "moisture", "value": 50},
        {"sensor_type": "moisture", "value": 70},
        {"sensor_type": "temp", "value": 20},
    ]
    avg = _average_sensor_data(entries)
    assert avg["moisture"] == 60
    assert avg["temp"] == 20


def test_compute_expected_uptake():
    totals = {"N": 30}
    expected, gap = _compute_expected_uptake("lettuce", "vegetative", totals)
    if expected:
        assert gap["N"] == round(expected["N"] - 30, 2)


def test_load_logs(tmp_path):
    pdir = tmp_path / "plant"
    pdir.mkdir()
    for name in (
        "irrigation_log.json",
        "nutrient_application_log.json",
        "sensor_reading_log.json",
        "water_quality_log.json",
        "yield_tracking_log.json",
    ):
        (pdir / name).write_text("[]")

    logs = _load_logs(pdir)
    assert all(isinstance(v, list) for v in logs.values())


def test_build_root_zone_info():
    general = {"max_root_depth_cm": 40}
    info = _build_root_zone_info(general, {"soil_moisture_pct": 50})
    assert info["taw_ml"] > 0
    assert info["current_moisture_pct"] == 50
