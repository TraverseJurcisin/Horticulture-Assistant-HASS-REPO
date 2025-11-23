import importlib
import json

from ..engine.plant_engine import constants


def test_get_stage_multiplier_default():
    assert constants.get_stage_multiplier("fruiting") == 1.1


def test_get_stage_multiplier_overlay(tmp_path, monkeypatch):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    sub = overlay / "stages"
    sub.mkdir()
    (sub / "stage_multipliers.json").write_text(json.dumps({"fruiting": 1.5}))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))
    importlib.reload(constants)
    try:
        assert constants.get_stage_multiplier("fruiting") == 1.5
    finally:
        monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR", raising=False)
        importlib.reload(constants)
