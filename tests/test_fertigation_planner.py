import importlib.util
import sys
from pathlib import Path

PACKAGE = "custom_components.horticulture_assistant.utils"
MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/utils/fertigation_planner.py"
spec = importlib.util.spec_from_file_location(f"{PACKAGE}.fertigation_planner", MODULE_PATH)
fertigation_planner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fertigation_planner
spec.loader.exec_module(fertigation_planner)

FertigationPlan = fertigation_planner.FertigationPlan
plan_fertigation_from_profile = fertigation_planner.plan_fertigation_from_profile


def _hass_for(base: Path):
    class DummyConfig:
        def __init__(self, base):
            self._base = Path(base)
        def path(self, name: str) -> str:
            return str(Path(base) / name)
    class DummyHass:
        def __init__(self, base):
            self.config = DummyConfig(base)
    return DummyHass(base)


def test_plan_fertigation_from_profile(tmp_path):
    (tmp_path / "plants").mkdir()
    (tmp_path / "plants/test.json").write_text(
        '{"general": {"plant_type": "citrus", "stage": "vegetative"}}'
    )
    hass = _hass_for(tmp_path)
    plan = plan_fertigation_from_profile("test", 5.0, hass)
    assert isinstance(plan, FertigationPlan)
    assert plan.schedule
    assert plan.cost_total >= 0


def test_plan_fertigation_missing_profile(tmp_path):
    hass = _hass_for(tmp_path)
    plan = plan_fertigation_from_profile("missing", 5.0, hass)
    assert plan.schedule == {}
    assert plan.cost_total == 0.0
