import json


from custom_components.horticulture_assistant.utils import plant_profile_loader as loader


def test_load_profile_from_json(tmp_path):
    data = {
        "general": {"plant_type": "test"},
        "thresholds": {"light": 100, "temperature": [20, 30], "EC": 1.2},
        "stages": {"seedling": {"stage_duration": 10}},
        "nutrients": {"N": 100}
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data))

    profile = loader.load_profile_from_path(path)
    assert profile["general"]["plant_type"] == "test"
    assert profile["thresholds"]["light"] == 100
    assert profile["stages"]["seedling"]["stage_duration"] == 10


def test_load_profile_from_yaml(tmp_path):
    yaml_content = """
    general:
      plant_type: tomato
    thresholds:
      light: 200
      temperature: [22, 30]
      EC: 2.0
    stages:
      seedling:
        stage_duration: 14
    """
    path = tmp_path / "tomato.yaml"
    path.write_text(yaml_content)

    profile = loader.load_profile_from_path(path)
    assert profile["general"]["plant_type"] == "tomato"
    assert profile["stages"]["seedling"]["stage_duration"] == 14


def test_parse_basic_yaml():
    content = "a: 1\nb:\n  c: 2\n  d: [3, 4]"
    result = loader.parse_basic_yaml(content)
    assert result == {"a": 1, "b": {"c": 2, "d": [3, 4]}}


def test_load_profile_by_id_custom_dir(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    (plants / "plant1.json").write_text("{}")

    profile = loader.load_profile_by_id("plant1", base_dir=plants)
    assert profile == {"general": {}, "thresholds": {}, "stages": {}, "nutrients": {}}


def test_load_profile_missing(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    monkeypatch_dir = plants
    orig = loader.DEFAULT_BASE_DIR
    try:
        loader.DEFAULT_BASE_DIR = monkeypatch_dir
        profile = loader.load_profile_by_id("missing")
    finally:
        loader.DEFAULT_BASE_DIR = orig
    assert profile == {}


def test_list_available_profiles(tmp_path):
    plants = tmp_path / "profiles"
    plants.mkdir()
    (plants / "one.json").write_text("{}")
    (plants / "two.yaml").write_text("general: {}")
    (plants / "skip.txt").write_text("bad")

    result = loader.list_available_profiles(plants)
    assert result == ["one", "two"]


def test_get_profile_path(tmp_path):
    base = tmp_path / "profiles"
    base.mkdir()
    file = base / "plantA.yaml"
    file.write_text("general: {}")

    path = loader.get_profile_path("plantA", base)
    assert path == file
    assert loader.get_profile_path("missing", base) is None


def test_save_and_update_sensors(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {"general": {"sensor_entities": {"moisture_sensors": ["old"]}}}
    assert loader.save_profile_by_id("p1", profile, plants)

    loader.update_profile_sensors(
        "p1",
        {"moisture_sensors": ["new"], "temperature_sensors": "temp1"},
        plants,
    )

    updated = json.load(open(plants / "p1.json", "r", encoding="utf-8"))
    sensors = updated["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["new"]
    assert sensors["temperature_sensors"] == ["temp1"]


def test_update_profile_sensors_missing(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()

    result = loader.update_profile_sensors("missing", {"moisture_sensors": ["x"]}, plants)
    assert result is False


def test_detach_profile_sensors(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {
        "general": {"sensor_entities": {"moisture_sensors": ["a", "b"], "temp_sensors": ["t1"]}}
    }
    loader.save_profile_by_id("p1", profile, plants)

    loader.detach_profile_sensors("p1", {"moisture_sensors": ["a"]}, plants)

    updated = json.load(open(plants / "p1.json", "r", encoding="utf-8"))
    sensors = updated["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["b"]
    assert sensors["temp_sensors"] == ["t1"]


def test_attach_profile_sensors(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {
        "general": {"sensor_entities": {"moisture_sensors": ["a"], "temp_sensors": ["t1"]}}
    }
    loader.save_profile_by_id("p1", profile, plants)

    loader.attach_profile_sensors("p1", {"moisture_sensors": ["b"]}, plants)

    updated = json.load(open(plants / "p1.json", "r", encoding="utf-8"))
    sensors = updated["general"]["sensor_entities"]
    assert sensors["moisture_sensors"] == ["a", "b"]
    assert sensors["temp_sensors"] == ["t1"]


def test_profile_exists_and_delete(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {}
    loader.save_profile_by_id("p1", profile, plants)

    assert loader.profile_exists("p1", plants)
    assert loader.delete_profile_by_id("p1", plants)
    assert not loader.profile_exists("p1", plants)


def test_default_base_dir_env(monkeypatch, tmp_path):
    env_dir = tmp_path / "envplants"
    env_dir.mkdir()
    monkeypatch.setenv("HORTICULTURE_PLANT_DIR", str(env_dir))
    assert loader.default_base_dir() == env_dir
    (env_dir / "x.json").write_text("{}")
    assert loader.get_profile_path("x") == env_dir / "x.json"
