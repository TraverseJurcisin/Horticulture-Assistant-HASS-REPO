import json

from custom_components.horticulture_assistant.automation import (
    fertilizer_actuator,
    irrigation_actuator,
    run_automation_cycle,
    run_fertilizer_cycle,
)


def test_run_automation_cycle(tmp_path, monkeypatch):
    plant_dir = tmp_path
    profile = {
        "plant_id": "plant1",
        "thresholds": {"soil_moisture": 30},
        "general": {"latest_env": {"soil_moisture": 20}},
        "actuators": {"irrigation": "switch.irrigate"},
    }
    (plant_dir / "plant1.json").write_text(json.dumps(profile))

    monkeypatch.setattr(run_automation_cycle, "ENABLE_AUTOMATION", True)
    called = {}

    def fake_trigger(plant_id: str, trigger: bool, base_path: str, hass=None):
        called["plant"] = plant_id
        called["trigger"] = trigger
        called["base"] = base_path

    monkeypatch.setattr(irrigation_actuator, "trigger_irrigation_actuator", fake_trigger)

    run_automation_cycle.run_automation_cycle(str(plant_dir))

    assert called["plant"] == "plant1"
    log = plant_dir / "plant1" / "irrigation_log.json"
    assert log.exists()
    data = json.loads(log.read_text())
    assert data and data[0]["triggered"] is True


def test_run_fertilizer_cycle(tmp_path, monkeypatch):
    plant_dir = tmp_path
    profile = {
        "plant_id": "p2",
        "thresholds": {"N": 20},
        "general": {"latest_env": {"N": 10}},
        "actuators": {"fertilizer": "switch.fert"},
    }
    (plant_dir / "p2.json").write_text(json.dumps(profile))

    monkeypatch.setattr(run_fertilizer_cycle, "ENABLE_AUTOMATION", True)
    called = {}

    def fake_trigger(plant_id: str, trigger: bool, base_path: str, hass=None):
        called["plant"] = plant_id
        called["trigger"] = trigger
        called["base"] = base_path

    monkeypatch.setattr(fertilizer_actuator, "trigger_fertilizer_actuator", fake_trigger)

    run_fertilizer_cycle.run_fertilizer_cycle(str(plant_dir))

    assert called["plant"] == "p2"
    log = plant_dir / "p2" / "nutrient_application_log.json"
    assert log.exists()
    data = json.loads(log.read_text())
    assert data and data[0]["triggered"] is True
