import json

from plant_engine import approval_queue
from plant_engine.utils import load_json


def test_queue_and_apply(tmp_path, monkeypatch):
    pending_dir = tmp_path / "pending"
    plant_path = tmp_path / "plant.json"
    plant_data = {"thresholds": {"soil_moisture_pct": 30}}
    plant_path.write_text(json.dumps(plant_data))

    monkeypatch.setattr(approval_queue, "PENDING_DIR", str(pending_dir))

    # Queue change
    approval_queue.queue_threshold_updates(
        "test",
        plant_data["thresholds"],
        {"soil_moisture_pct": 35, "ec": 1.5},
    )

    pending_file = pending_dir / "test.json"
    assert pending_file.exists()

    # Approve one change
    pending = load_json(str(pending_file))
    pending["changes"]["soil_moisture_pct"]["status"] = "approved"
    pending_file.write_text(json.dumps(pending))

    # Apply
    approval_queue.apply_approved_thresholds(str(plant_path), str(pending_file))
    updated = load_json(str(plant_path))
    assert updated["thresholds"]["soil_moisture_pct"] == 35
    assert "ec" not in updated["thresholds"]
