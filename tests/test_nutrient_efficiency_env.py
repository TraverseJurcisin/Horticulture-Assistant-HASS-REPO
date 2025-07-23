import importlib
import json

import plant_engine.nutrient_efficiency as ne


def test_env_overrides(tmp_path, monkeypatch):
    nutrient_dir = tmp_path / "nutes"
    yield_dir = tmp_path / "yield"
    nutrient_dir.mkdir()
    yield_dir.mkdir()
    (nutrient_dir / "foo.json").write_text(json.dumps({"records": []}))
    (yield_dir / "foo.json").write_text(json.dumps({"harvests": []}))

    monkeypatch.setenv("HORTICULTURE_NUTRIENT_DIR", str(nutrient_dir))
    monkeypatch.setenv("HORTICULTURE_YIELD_DIR", str(yield_dir))
    importlib.reload(ne)

    assert ne.NUTRIENT_DIR == str(nutrient_dir)
    assert ne.YIELD_DIR == str(yield_dir)
