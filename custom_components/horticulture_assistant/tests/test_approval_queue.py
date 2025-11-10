import json

from plant_engine.utils import load_json

from plant_engine import approval_queue


def test_queue_and_apply(tmp_path, monkeypatch):
    pending_dir = tmp_path / "pending"
    plant_path = tmp_path / "plant.json"
    plant_data = {"thresholds": {"soil_moisture_pct": 30}}
    plant_path.write_text(json.dumps(plant_data))

    monkeypatch.setattr(approval_queue, "PENDING_DIR", pending_dir)

    # Queue change
    approval_queue.queue_threshold_updates(
        "test",
        plant_data["thresholds"],
        {"soil_moisture_pct": 35, "ec": 1.5},
    )

    pending_file = pending_dir / "test.json"
    assert pending_file.exists()
    pending_data = approval_queue.list_pending_changes("test", pending_dir)
    assert pending_data["changes"]["soil_moisture_pct"]["proposed_value"] == 35

    # Approve one change
    pending = load_json(pending_file)
    pending["changes"]["soil_moisture_pct"]["status"] = "approved"
    pending_file.write_text(json.dumps(pending))

    # Apply
    approval_queue.apply_approved_thresholds(plant_path, pending_file)
    updated = load_json(plant_path)
    assert updated["thresholds"]["soil_moisture_pct"] == 35
    assert "ec" not in updated["thresholds"]


def test_apply_approved_thresholds_missing_files(tmp_path, caplog):
    plant_path = tmp_path / "missing.json"
    pending_path = tmp_path / "pending.json"
    caplog.set_level("ERROR")

    count = approval_queue.apply_approved_thresholds(plant_path, pending_path)
    assert count == 0
    assert any("Pending threshold file not found" in r.message for r in caplog.records)

    # create pending file but missing plant profile
    pending_path.write_text("{}")
    caplog.clear()
    count = approval_queue.apply_approved_thresholds(plant_path, pending_path)
    assert count == 0
    assert any("Plant profile not found" in r.message for r in caplog.records)
