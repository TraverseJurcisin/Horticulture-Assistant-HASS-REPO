import json

from plant_engine.utils import load_json

from custom_components.horticulture_assistant.engine.push_to_approval_queue import (
    push_to_approval_queue,
)


def test_push_to_approval_queue(tmp_path):
    base = tmp_path
    plants = base / "plants"
    plants.mkdir()
    data_dir = base / "data" / "pending_thresholds"
    data_dir.mkdir(parents=True)
    profile = {"thresholds": {"ec": 1.5}}
    (plants / "foo.json").write_text(json.dumps(profile))

    record = push_to_approval_queue("foo", {"ec": 2.0, "ph": 6.2}, base)
    assert record["plant_id"] == "foo"
    path = data_dir / "foo.json"
    assert path.exists()
    saved = load_json(path)
    assert saved["changes"]["ec"]["proposed_value"] == 2.0
    assert saved["changes"]["ec"]["previous_value"] == 1.5
