import json

from custom_components.horticulture_assistant.utils.load_plant_profile import \
    load_plant_profile


def test_load_profile_basic(tmp_path):
    plant_dir = tmp_path / "plants" / "demo"
    plant_dir.mkdir(parents=True)
    (plant_dir / "general.json").write_text(json.dumps({"name": "demo"}))
    (plant_dir / "thresholds.json").write_text("{}")
    (plant_dir / "profile_index.json").write_text("{}")
    profile = load_plant_profile("demo", base_path=tmp_path / "plants")
    assert profile.plant_id == "demo"
    assert "general" in profile.profile_data
    assert "profile_index" not in profile.profile_data


def test_load_profile_with_validation_files(tmp_path):
    plant_dir = tmp_path / "plants" / "demo"
    plant_dir.mkdir(parents=True)
    (plant_dir / "general.json").write_text("{}")
    (plant_dir / "validate_extra.json").write_text("{}")

    result = load_plant_profile("demo", base_path=tmp_path / "plants")
    assert "validate_extra" not in result.profile_data

    result = load_plant_profile(
        "demo",
        base_path=tmp_path / "plants",
        include_validation_files=True,
    )
    assert "validate_extra" in result.profile_data


def test_load_profile_missing_dir(tmp_path):
    result = load_plant_profile("missing", base_path=tmp_path / "plants")
    assert result == {}
