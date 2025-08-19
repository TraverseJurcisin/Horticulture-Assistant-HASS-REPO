import json
from custom_components.horticulture_assistant.automation.irrigation_trigger import (
    irrigation_trigger,
)
from custom_components.horticulture_assistant.automation.fertilizer_trigger import (
    fertilizer_trigger,
)


def test_irrigation_trigger(tmp_path):
    profile = {
        "plant_id": "p1",
        "thresholds": {"soil_moisture": 30},
        "general": {"latest_env": {"soil_moisture": 20}},
    }
    (tmp_path / "p1.json").write_text(json.dumps(profile))

    assert irrigation_trigger("p1", base_path=str(tmp_path)) is True
    assert (
        irrigation_trigger(
            "p1",
            base_path=str(tmp_path),
            sensor_data={"soil_moisture": 40},
        )
        is False
    )


def test_fertilizer_trigger(tmp_path):
    profile = {
        "plant_id": "p2",
        "thresholds": {"N": 10},
        "general": {"latest_env": {"N": 5}},
    }
    (tmp_path / "p2.json").write_text(json.dumps(profile))

    assert fertilizer_trigger("p2", base_path=str(tmp_path)) is True
    assert (
        fertilizer_trigger(
            "p2",
            base_path=str(tmp_path),
            sensor_data={"N": 15},
        )
        is False
    )
