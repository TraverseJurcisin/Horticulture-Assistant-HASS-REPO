import json
from pathlib import Path

import scripts.profile_manager as pm


def test_load_default_profile(tmp_path: Path):
    global_dir = tmp_path / "data/global_profiles"
    global_dir.mkdir(parents=True)
    sample = {
        "general": {"plant_type": "demo", "cultivar": "std"},
        "thresholds": {"soil_moisture_pct": 10},
    }
    (global_dir / "demo.json").write_text(json.dumps(sample))
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()

    ok = pm.load_default_profile("demo", "demo1", plants_dir, global_dir)
    assert ok
    created = json.load(open(plants_dir / "demo1.json", "r", encoding="utf-8"))
    assert created["general"]["plant_id"] == "demo1"
    assert created["general"]["plant_type"] == "demo"


def test_show_history(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plant_home = plants_dir / "demo"
    plant_home.mkdir(parents=True)
    log_data = [{"val": i} for i in range(5)]
    (plant_home / "events.json").write_text(json.dumps(log_data))

    entries = pm.show_history("demo", "events", plants_dir, lines=2)
    assert entries == log_data[-2:]


def test_list_profile_sensors(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    profile = {
        "general": {
            "sensor_entities": {"moisture_sensors": ["a"], "temp_sensors": ["t"]}
        }
    }
    (plants_dir / "p1.json").write_text(json.dumps(profile))

    sensors = pm.list_profile_sensors("p1", plants_dir)
    assert sensors == profile["general"]["sensor_entities"]


def test_list_global_profiles(tmp_path: Path):
    global_dir = tmp_path / "data/global_profiles"
    global_dir.mkdir(parents=True)
    (global_dir / "a.json").write_text("{}")
    (global_dir / "b.json").write_text("{}")

    profiles = pm.list_global_profiles(global_dir)
    assert profiles == ["a", "b"]


def test_show_global_profile(tmp_path: Path):
    global_dir = tmp_path / "data/global_profiles"
    global_dir.mkdir(parents=True)
    data = {"general": {"plant_type": "demo"}}
    (global_dir / "demo.json").write_text(json.dumps(data))

    result = pm.show_global_profile("demo", global_dir)
    assert result["general"]["plant_type"] == "demo"


def test_show_preferences_and_logs(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plant_home = plants_dir / "p1"
    plant_home.mkdir(parents=True)
    profile = {"general": {"auto_approve_all": True, "sensor_entities": {"m": ["a"]}}}
    (plants_dir / "p1.json").write_text(json.dumps(profile))
    (plant_home / "events.json").write_text("[]")
    (plant_home / "metrics.json").write_text("[]")

    prefs = pm.show_preferences("p1", plants_dir)
    assert prefs["auto_approve_all"] is True
    assert "sensor_entities" not in prefs

    logs = pm.list_log_files("p1", plants_dir)
    assert logs == ["events", "metrics"]


def test_attach_and_detach_sensor(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    profile = {"general": {"sensor_entities": {"moisture_sensors": ["a"]}}}
    (plants_dir / "p1.json").write_text(json.dumps(profile))

    ok = pm.attach_sensor("p1", "moisture_sensors", ["b"], plants_dir)
    assert ok
    sensors = json.load(open(plants_dir / "p1.json", "r", encoding="utf-8"))["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["a", "b"]

    ok = pm.detach_sensor("p1", "moisture_sensors", ["a"], plants_dir)
    assert ok
    sensors = json.load(open(plants_dir / "p1.json", "r", encoding="utf-8"))["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["b"]
