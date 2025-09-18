import importlib
import json

import plant_engine.constants as const
import plant_engine.utils as utils


def test_default_environment_loaded(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "environment").mkdir()
    (data_dir / "environment" / "default_environment.json").write_text(json.dumps({"temp_c": 20, "rh_pct": 55}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    importlib.reload(const)

    assert const.DEFAULT_ENV["temp_c"] == 20
    assert const.DEFAULT_ENV["rh_pct"] == 55
    # ensure fallback values still present
    assert const.DEFAULT_ENV["par_w_m2"] == 350


def test_default_environment_overlay(tmp_path, monkeypatch):
    base = tmp_path / "data"
    overlay = tmp_path / "overlay"
    base.mkdir()
    overlay.mkdir()
    (base / "environment").mkdir()
    (overlay / "environment").mkdir()
    (base / "environment" / "default_environment.json").write_text(json.dumps({"temp_c": 20}))
    (overlay / "environment" / "default_environment.json").write_text(json.dumps({"temp_c": 24}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))

    importlib.reload(utils)
    importlib.reload(const)

    assert const.DEFAULT_ENV["temp_c"] == 24
