from pathlib import Path
import shutil
import importlib.util
import sys
import types
import json
import plant_engine.utils as utils

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components/horticulture_assistant/utils/nutrient_scheduler.py"
)
spec = importlib.util.spec_from_file_location("nutrient_scheduler", MODULE_PATH)
nutrient_scheduler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nutrient_scheduler
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    ha.core = types.ModuleType("homeassistant.core")
    ha.core.HomeAssistant = object
    ha.config_entries = types.ModuleType("homeassistant.config_entries")
    ha.config_entries.ConfigEntry = object
    ha.helpers = types.ModuleType("homeassistant.helpers")
    ha.helpers.typing = types.ModuleType("homeassistant.helpers.typing")
    ha.helpers.typing.ConfigType = dict
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = ha.core
    sys.modules["homeassistant.config_entries"] = ha.config_entries
    sys.modules["homeassistant.helpers"] = ha.helpers
    sys.modules["homeassistant.helpers.typing"] = ha.helpers.typing
spec.loader.exec_module(nutrient_scheduler)
schedule_nutrients = nutrient_scheduler.schedule_nutrients
NutrientTargets = nutrient_scheduler.NutrientTargets

ROOT = Path(__file__).resolve().parents[1]


def test_schedule_nutrients_dataset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(ROOT / "plant_registry.json", tmp_path / "plant_registry.json")
    (tmp_path / "plants").mkdir()
    shutil.copy(ROOT / "plants/citrus_backyard_spring2025.json", tmp_path / "plants/citrus_backyard_spring2025.json")

    class DummyConfig:
        def __init__(self, base):
            self._base = Path(base)

        def path(self, name):
            return str(self._base / name)

    class DummyHass:
        def __init__(self, base):
            self.config = DummyConfig(base)

    hass = DummyHass(tmp_path)

    result = schedule_nutrients("citrus_backyard_spring2025", hass=hass).as_dict()
    # citrus fruiting guidelines N=120, K=100 with stage multiplier 1.1
    # absorption rates adjust N by 1/0.65 and K by 1/0.9
    assert result["N"] == 203.08
    assert result["K"] == 122.22


def _hass_for(tmp_path: Path) -> object:
    class DummyConfig:
        def __init__(self, base: Path):
            self._base = base

        def path(self, name: str) -> str:
            return str(self._base / name)

    class DummyHass:
        def __init__(self, base: Path):
            self.config = DummyConfig(base)

    return DummyHass(tmp_path)


def test_stage_synonym_resolution(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "test.json").write_text('{"general": {"plant_type": "strawberry", "stage": "veg"}}')
    hass = _hass_for(tmp_path)
    result = schedule_nutrients("test", hass=hass).as_dict()
    assert result["N"] == 93.33


def test_tag_based_modifier(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "tag.json").write_text('{"general": {"plant_type": "lettuce", "stage": "seedling", "tags": ["high-nitrogen"]}}')
    hass = _hass_for(tmp_path)
    result = schedule_nutrients("tag", hass=hass).as_dict()
    assert result["N"] == 80.0


def test_dataset_override(tmp_path, monkeypatch):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "nutrient_tag_modifiers.json").write_text(
        json.dumps({"test-tag": {"N": 1.5}})
    )
    assert (overlay / "nutrient_tag_modifiers.json").exists()
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))
    import importlib
    importlib.reload(utils)
    nutrient_scheduler.load_dataset = utils.load_dataset
    utils.load_dataset.cache_clear()
    nutrient_scheduler._tag_modifiers.cache_clear()

    assert nutrient_scheduler._tag_modifiers()["test_tag"]["N"] == 1.5

    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "tag.json").write_text(
        '{"general": {"plant_type": "lettuce", "stage": "seedling", "tags": ["test-tag"]}}'
    )
    hass = _hass_for(tmp_path)
    result = schedule_nutrients("tag", hass=hass).as_dict()
    assert result["N"] == 100.0
    monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR", raising=False)


def test_include_micro_guidelines(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "micro.json").write_text(
        '{"general": {"plant_type": "lettuce", "stage": "seedling"}}'
    )
    hass = _hass_for(tmp_path)
    result = schedule_nutrients("micro", hass=hass, include_micro=True).as_dict()
    assert result["Fe"] > 0


def test_schedule_nutrient_corrections(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "corr.json").write_text(
        '{"general": {"plant_type": "lettuce", "stage": "seedling"}}'
    )
    hass = _hass_for(tmp_path)
    from custom_components.horticulture_assistant.utils import nutrient_scheduler as ns

    adjustments = ns.schedule_nutrient_corrections(
        "corr", {"N": 0.0, "P": 0.0, "K": 0.0}, hass=hass
    ).as_dict()
    assert adjustments["N"] > 0


def test_schedule_nutrients_bulk(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    (plant_dir / "p1.json").write_text(
        '{"general": {"plant_type": "lettuce", "stage": "seedling"}}'
    )
    (plant_dir / "p2.json").write_text(
        '{"general": {"plant_type": "lettuce", "stage": "harvest"}}'
    )
    hass = _hass_for(tmp_path)
    from custom_components.horticulture_assistant.utils import nutrient_scheduler as ns

    result = ns.schedule_nutrients_bulk(["p1", "p2"], hass=hass)
    assert result["p1"]["N"] > 0
    assert result["p2"]["N"] > 0


def test_absorption_rates_applied(tmp_path):
    plant_dir = tmp_path / "plants"
    plant_dir.mkdir()
    # lettuce seedling profile with no explicit nutrients
    (plant_dir / "lettuce.json").write_text('{"general": {"plant_type": "lettuce", "stage": "seedling"}}')
    hass = _hass_for(tmp_path)
    result = schedule_nutrients("lettuce", hass=hass).as_dict()
    # guideline N=80 with stage multiplier 0.5 => 40 then adjusted by absorption 1/0.6
    assert result["N"] == 66.67
