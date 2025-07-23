import json
from pathlib import Path

from custom_components.horticulture_assistant.analytics.export_all_growth_yield import (
    export_all_growth_yield,
)


def test_export_all_growth_yield(tmp_path: Path):
    base = tmp_path / "analytics"
    base.mkdir()
    (base / "plant1_growth_yield.json").write_text(json.dumps([{"date": "2024-01-01", "yield": 10}]))
    (base / "plant2_growth_yield.json").write_text(json.dumps([{"date": "2024-01-02", "yield": 5}]))

    result = export_all_growth_yield(base)
    assert set(result.keys()) == {"plant1", "plant2"}
    assert result["plant1"][0]["date"] == "2024-01-01"
