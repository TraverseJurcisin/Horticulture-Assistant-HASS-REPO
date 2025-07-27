import importlib
import json

import plant_engine.utils as utils
import plant_engine.constants as const


def test_default_environment_loaded(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "default_environment.json").write_text(
        json.dumps({"temp_c": 20, "rh_pct": 55})
    )

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
    (base / "default_environment.json").write_text(json.dumps({"temp_c": 20}))
    (overlay / "default_environment.json").write_text(json.dumps({"temp_c": 24}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))

    importlib.reload(utils)
    importlib.reload(const)

    assert const.DEFAULT_ENV["temp_c"] == 24


def test_default_environment_dataclass(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "default_environment.json").write_text(
        json.dumps({"temp_c": 18, "rh_pct": 50})
    )

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))

    importlib.reload(utils)
    importlib.reload(const)

    env = const.load_default_environment()
    assert env.temp_c == 18
    assert env.rh_pct == 50
    assert env.as_dict() == const.DEFAULT_ENV
