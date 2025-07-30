import json
from datetime import datetime, timedelta, timezone
from custom_components.horticulture_assistant.engine.run_daily_cycle import _load_recent_entries

def test_load_recent_entries(tmp_path):
    log = tmp_path / "log.json"
    now = datetime.now(timezone.utc)
    old = {"timestamp": (now - timedelta(hours=30)).isoformat(), "v": 1}
    recent = {"timestamp": (now - timedelta(hours=5)).isoformat(), "v": 2}
    log.write_text(json.dumps([old, recent]))
    result = _load_recent_entries(log, hours=24)
    assert result == [recent]
