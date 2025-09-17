import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(
    "custom_components/horticulture_assistant/data/fertilizers/schema/2025-09-V3e.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def test_fertilizer_json_valid() -> None:
    data_dir = Path("custom_components/horticulture_assistant/data/fertilizers/detail")
    for path in data_dir.rglob("*.json"):
        obj = json.loads(path.read_text())
        VALIDATOR.validate(obj)
