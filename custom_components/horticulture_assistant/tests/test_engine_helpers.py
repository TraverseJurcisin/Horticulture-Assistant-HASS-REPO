import json
from pathlib import Path

from ..engine.plant_engine import engine


def test_generate_environment_actions(tmp_path, monkeypatch):
    profile = {
        "plant_type": "citrus",
        "stage": "vegetative",
        "observed_pests": ["aphids"],
        "observed_diseases": ["root rot"],
    }
    env = {"temp_c": 24, "rh_pct": 60, "par_w_m2": 300}
    # Use real dataset; function should work without patching
    actions = engine._generate_environment_actions(profile, env)
    env_actions, pest_actions, disease_actions = actions
    assert isinstance(env_actions, dict)
    assert pest_actions.get("aphids")
    assert disease_actions.get("root rot")


def test_get_nutrient_targets():
    profile = {"plant_type": "citrus", "stage": "vegetative"}
    guidelines, targets = engine._get_nutrient_targets(profile)
    assert guidelines
    assert targets


def test_write_report(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "OUTPUT_DIR", str(tmp_path))
    data = {"a": 1}
    engine._write_report("demo", data)
    out_file = Path(tmp_path) / "demo.json"
    assert out_file.exists()
    assert json.loads(out_file.read_text()) == data
