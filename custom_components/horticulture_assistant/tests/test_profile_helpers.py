import json

from ..utils.profile_helpers import write_profile_sections


def test_write_profile_sections_creates_files(tmp_path):
    sections = {
        "general.json": {"name": "demo"},
        "stages.json": {"seedling": {"d": 1}},
    }
    pid = write_profile_sections("demo", sections, base_path=tmp_path)
    assert pid == "demo"
    for name in sections:
        path = tmp_path / "demo" / name
        assert path.exists()
        with open(path, encoding="utf-8") as f:
            assert json.load(f) == sections[name]


def test_write_profile_sections_overwrite(tmp_path):
    base = tmp_path / "demo"
    base.mkdir()
    (base / "general.json").write_text("{}", encoding="utf-8")
    pid = write_profile_sections(
        "demo",
        {"general.json": {"name": "updated"}},
        base_path=tmp_path,
        overwrite=True,
    )
    assert pid == "demo"
    with open(base / "general.json", encoding="utf-8") as f:
        assert json.load(f)["name"] == "updated"


def test_write_profile_sections_sanitises_windows_reserved_name(tmp_path):
    sections = {"general.json": {"name": "demo"}}

    pid = write_profile_sections("CON", sections, base_path=tmp_path)

    assert pid == "CON"
    path = tmp_path / "con_profile" / "general.json"
    assert path.exists()


def test_write_profile_sections_strips_invalid_path_characters(tmp_path):
    sections = {"general.json": {"name": "demo"}}

    pid = write_profile_sections("demo:plant*", sections, base_path=tmp_path)

    assert pid == "demo:plant*"
    path = tmp_path / "demo_plant_" / "general.json"
    assert path.exists()
