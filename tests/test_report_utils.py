from datetime import datetime, timedelta
import json
from plant_engine.report_utils import load_recent_entries


def test_load_recent_entries(tmp_path):
    entries = [
        {"timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(), "v": 1},
        {"timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(), "v": 2},
    ]
    path = tmp_path / "log.json"
    path.write_text(json.dumps(entries))

    recent = load_recent_entries(path, hours=1)
    assert len(recent) == 1
    assert recent[0]["v"] == 1


def test_load_recent_entries_missing(tmp_path):
    path = tmp_path / "missing.json"
    assert load_recent_entries(path) == []
