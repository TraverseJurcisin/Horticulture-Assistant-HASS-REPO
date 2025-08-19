import json
import os
from custom_components.horticulture_assistant.utils.load_all_profiles import (
    load_all_profiles,
    ProfileLoadResult,
)


def _make_profile(base: str, pid: str, extra: dict | None = None) -> None:
    os.makedirs(f"{base}/plants/{pid}", exist_ok=True)
    data = {"name": pid}
    if extra:
        data.update(extra)
    with open(f"{base}/plants/{pid}/general.json", "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_load_all_profiles_basic(tmp_path):
    _make_profile(tmp_path, "demo")

    result = load_all_profiles(base_path=tmp_path / "plants")
    assert "demo" in result
    res = result["demo"]
    assert isinstance(res, ProfileLoadResult)
    assert res.plant_id == "demo"
    assert res.loaded
    assert "general" in res.profile_data
    assert res.issues == {}


def test_load_all_profiles_pattern(tmp_path):
    os.makedirs(tmp_path / "plants/test", exist_ok=True)
    with open(tmp_path / "plants/test" / "data_one.json", "w", encoding="utf-8") as f:
        json.dump({"a": 1}, f)
    with open(tmp_path / "plants/test" / "skip.txt", "w", encoding="utf-8") as f:
        f.write("bad")

    result = load_all_profiles(base_path=tmp_path / "plants", pattern="data_*.json")
    assert "test" in result
    res = result["test"]
    assert res.plant_id == "test"
    assert "data_one" in res.profile_data
    assert "skip" not in res.profile_data
