import csv
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
    with open(plants_dir / "demo1.json", encoding="utf-8") as file:
        created = json.load(file)
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


def test_show_history_prefers_jsonl(tmp_path: Path):
    history_root = tmp_path / "history"
    profile_history = history_root / "demo"
    profile_history.mkdir(parents=True)
    log_data = [{"val": i} for i in range(4)]
    history_path = profile_history / "events.jsonl"
    history_path.write_text("\n".join(json.dumps(item) for item in log_data) + "\n")

    entries = pm.show_history(
        "demo",
        "events",
        tmp_path / "plants",
        lines=3,
        history_dir=history_root,
    )

    assert entries == log_data[-3:]


def test_list_profile_sensors(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    profile = {"general": {"sensor_entities": {"moisture_sensors": ["a"], "temp_sensors": ["t"]}}}
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


def test_export_history_csv(tmp_path: Path):
    history_root = tmp_path / "history"
    profile_history = history_root / "demo"
    profile_history.mkdir(parents=True)
    entries = [
        {"harvested_at": "2024-01-01T00:00:00Z", "mass_g": 250, "meta": {"note": "early"}},
        {"harvested_at": "2024-02-01T00:00:00Z", "mass_g": 300, "meta": {"note": "late"}},
    ]
    log_path = profile_history / "harvest_events.jsonl"
    log_path.write_text("\n".join(json.dumps(item) for item in entries) + "\n")

    out_path = tmp_path / "out" / "harvests.csv"
    result = pm.export_history(
        "demo",
        "harvest_events",
        out_path,
        fmt="csv",
        history_dir=history_root,
    )

    assert result == out_path
    rows = list(csv.DictReader(out_path.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["mass_g"] == "250"
    assert json.loads(rows[1]["meta"]) == {"note": "late"}


def test_export_history_limit(tmp_path: Path):
    history_root = tmp_path / "history"
    profile_history = history_root / "demo"
    profile_history.mkdir(parents=True)
    entries = [{"val": i} for i in range(4)]
    log_path = profile_history / "run_events.jsonl"
    log_path.write_text("\n".join(json.dumps(item) for item in entries) + "\n")

    out_path = tmp_path / "out.jsonl"
    pm.export_history(
        "demo",
        "run_events",
        out_path,
        fmt="jsonl",
        limit=2,
        history_dir=history_root,
    )

    exported = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line]
    assert exported == entries[-2:]


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
    history_root = tmp_path / "history"
    history_profile = history_root / "p1"
    history_profile.mkdir(parents=True)
    (history_profile / "harvest_events.jsonl").write_text("{}\n")

    prefs = pm.show_preferences("p1", plants_dir)
    assert prefs["auto_approve_all"] is True
    assert "sensor_entities" not in prefs

    logs = pm.list_log_files("p1", plants_dir, history_dir=history_root)
    assert logs == ["events", "harvest_events", "metrics"]


def test_attach_and_detach_sensor(tmp_path: Path):
    plants_dir = tmp_path / "plants"
    plants_dir.mkdir()
    profile = {"general": {"sensor_entities": {"moisture_sensors": ["a"]}}}
    (plants_dir / "p1.json").write_text(json.dumps(profile))

    ok = pm.attach_sensor("p1", "moisture_sensors", ["b"], plants_dir)
    assert ok
    with open(plants_dir / "p1.json", encoding="utf-8") as file:
        sensors = json.load(file)["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["a", "b"]

    ok = pm.detach_sensor("p1", "moisture_sensors", ["a"], plants_dir)
    assert ok
    with open(plants_dir / "p1.json", encoding="utf-8") as file:
        sensors = json.load(file)["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["b"]
