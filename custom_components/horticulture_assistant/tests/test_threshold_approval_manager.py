import json
from pathlib import Path
import sys
import types

# Minimal Home Assistant stub so the module imports without the real package
ha = types.ModuleType("homeassistant")
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.core", ha.core)

from custom_components.horticulture_assistant.utils import threshold_approval_manager as tam


class DummyConfig:
    def __init__(self, base: Path):
        self._base = Path(base)

    def path(self, *parts: str) -> str:
        return str(self._base.joinpath(*parts))


class DummyHass:
    def __init__(self, base: Path):
        self.config = DummyConfig(base)


def test_apply_threshold_approvals(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    plants_dir = tmp_path / "plants"
    data_dir.mkdir()
    plants_dir.mkdir()

    pending = {
        "plant1": {
            "changes": {
                "light": {"previous_value": 100, "proposed_value": 150, "status": "approved"},
                "humidity": {"previous_value": 50, "proposed_value": 55, "status": "pending"},
            }
        }
    }
    (data_dir / "pending_approvals.json").write_text(json.dumps(pending))

    profile = {"thresholds": {"light": 100, "humidity": 50}}
    (plants_dir / "plant1.json").write_text(json.dumps(profile))

    hass = DummyHass(tmp_path)

    tam.apply_threshold_approvals(hass)

    updated = json.loads((plants_dir / "plant1.json").read_text())
    assert updated["thresholds"]["light"] == 150
    assert updated["thresholds"]["humidity"] == 50

    remaining = json.loads((data_dir / "pending_approvals.json").read_text())
    assert "light" not in remaining["plant1"]["changes"]


def test_apply_threshold_approvals_list_format(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    plants_dir = tmp_path / "plants"
    data_dir.mkdir()
    plants_dir.mkdir()

    pending = [
        {
            "plant_id": "plant1",
            "changes": {
                "ec": {"previous_value": 1, "proposed_value": 2, "status": "approved"}
            },
        },
        {
            "plant_id": "plant2",
            "changes": {
                "ph": {"previous_value": 5.5, "proposed_value": 6, "status": "pending"}
            },
        },
    ]
    (data_dir / "pending_approvals.json").write_text(json.dumps(pending))

    (plants_dir / "plant1.json").write_text(json.dumps({"thresholds": {"ec": 1}}))
    (plants_dir / "plant2.json").write_text(json.dumps({"thresholds": {"ph": 5.5}}))

    hass = DummyHass(tmp_path)

    tam.apply_threshold_approvals(hass)

    updated = json.loads((plants_dir / "plant1.json").read_text())
    assert updated["thresholds"]["ec"] == 2

    remaining = json.loads((data_dir / "pending_approvals.json").read_text())
    assert isinstance(remaining, list)
    assert len(remaining) == 1
    assert remaining[0]["plant_id"] == "plant2"
