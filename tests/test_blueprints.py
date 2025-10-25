import pathlib

import pytest
import yaml

BLUEPRINT_ROOT = pathlib.Path(__file__).resolve().parents[1] / "blueprints" / "automation" / "horticulture_assistant"


@pytest.mark.parametrize(
    "blueprint_file",
    sorted(BLUEPRINT_ROOT.glob("*.yaml")),
    ids=lambda path: path.stem,
)
def test_blueprint_metadata(blueprint_file: pathlib.Path) -> None:
    data = yaml.safe_load(blueprint_file.read_text())
    assert "blueprint" in data, "missing blueprint header"
    header = data["blueprint"]
    assert header.get("domain") == "automation"
    assert "name" in header and header["name"].startswith("Horticulture Assistant"), "unexpected name"
    assert "input" in header and header["input"], "blueprint must declare inputs"


def test_harvest_notification_defaults() -> None:
    data = yaml.safe_load((BLUEPRINT_ROOT / "harvest_notification.yaml").read_text())
    inputs = data["blueprint"]["input"]
    assert "plant_device" in inputs
    actions = inputs["actions"]
    default_actions = actions.get("default")
    assert isinstance(default_actions, list)
    assert default_actions[0]["service"] == "persistent_notification.create"


def test_scheduled_irrigation_blueprint_structure() -> None:
    data = yaml.safe_load((BLUEPRINT_ROOT / "scheduled_irrigation_log.yaml").read_text())
    trigger = data["automation"]["trigger"]
    assert isinstance(trigger, list)
    first = trigger[0]
    assert "minutes" in first
    assert first["minutes"].startswith("/")
    action = data["automation"]["action"]
    assert action[0]["service"] == "horticulture_assistant.record_cultivation_event"


def test_status_recovery_watchdog_blueprint() -> None:
    data = yaml.safe_load((BLUEPRINT_ROOT / "status_recovery_watchdog.yaml").read_text())
    blueprint = data["blueprint"]
    assert blueprint["name"].endswith("Status recovery watchdog")
    automation = data["automation"]
    assert automation.get("mode") == "restart"
    choose = automation["action"][1]["choose"][0]
    condition = choose["conditions"][0]
    assert condition["type"] == "status_problem"
    assert condition["domain"] == "horticulture_assistant"
