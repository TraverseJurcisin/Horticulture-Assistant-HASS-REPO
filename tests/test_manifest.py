import json
from pathlib import Path


def test_manifest_metadata():
    manifest_path = Path("custom_components/horticulture_assistant/manifest.json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["domain"] == "horticulture_assistant"
    assert isinstance(data.get("name"), str) and data["name"].strip()
    assert data.get("loggers") == ["custom_components.horticulture_assistant"]
    assert data.get("integration_type") == "hub"
