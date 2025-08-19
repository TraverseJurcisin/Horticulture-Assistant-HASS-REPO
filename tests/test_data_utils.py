import json
import builtins
import pytest

from custom_components.horticulture_assistant.utils.data import load_large_json


@pytest.mark.asyncio
async def test_load_large_json_caches(hass, tmp_path, monkeypatch):
    file = tmp_path / "data.json"
    file.write_text(json.dumps({"a": 1}))

    opened = 0
    real_open = builtins.open

    def fake_open(path, mode="r", encoding="utf-8"):
        nonlocal opened
        opened += 1
        return real_open(path, mode, encoding=encoding)

    monkeypatch.setattr("builtins.open", fake_open)

    data1 = await load_large_json(hass, str(file))
    data2 = await load_large_json(hass, str(file))

    assert data1 == {"a": 1}
    assert data2 == {"a": 1}
    assert opened == 1
