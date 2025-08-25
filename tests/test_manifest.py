import json
import pathlib


def test_manifest_metadata():
    manifest_path = (
        pathlib.Path(__file__).parents[1]
        / "custom_components"
        / "horticulture_assistant"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    assert manifest["domain"] == "horticulture_assistant"
    assert manifest.get("after_dependencies") == ["recorder"]
    assert manifest.get("integration_type") == "helper"
    assert manifest.get("iot_class") == "calculated"
    assert manifest.get("quality_scale") == "bronze"
    assert manifest.get("version") == "2025.08.0"
    assert manifest.get("loggers") == ["custom_components.horticulture_assistant"]
