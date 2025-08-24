import json
from pathlib import Path

import jsonschema

SCHEMA = json.loads(
    Path(
        "custom_components/horticulture_assistant/schemas/fertilizer_detail.schema.json"
    ).read_text()
)


def test_fertilizer_json_valid():
    data_dir = Path("custom_components/horticulture_assistant/data/fertilizers/detail")
    for path in data_dir.rglob("*.json"):
        obj = json.loads(path.read_text())
        jsonschema.validate(obj, SCHEMA)
