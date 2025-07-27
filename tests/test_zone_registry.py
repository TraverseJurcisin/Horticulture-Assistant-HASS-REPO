from custom_components.horticulture_assistant.utils.zone_registry import (
    ZoneConfig,
    load_zones,
    get_zone,
    list_zones,
    save_zones,
    add_zone,
    attach_plants,
    detach_plants,
    attach_solenoids,
    detach_solenoids,
)


def test_zone_registry_roundtrip(tmp_path, monkeypatch):
    data = {
        "1": {"solenoids": ["a"], "plant_ids": ["p1"]},
        "2": {"solenoids": ["b", "c"], "plant_ids": []},
    }
    file_path = tmp_path / "zones.json"
    file_path.write_text("{}")

    def fake_config_path(hass, *parts):
        return str(file_path)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.zone_registry.config_path",
        fake_config_path,
    )

    zones = {zid: ZoneConfig(zid, info["solenoids"], info["plant_ids"]) for zid, info in data.items()}
    assert save_zones(zones)
    loaded = load_zones()
    assert set(loaded.keys()) == {"1", "2"}
    assert get_zone("1").solenoids == ["a"]
    assert list_zones() == ["1", "2"]


def test_zone_registry_modify(tmp_path, monkeypatch):
    file_path = tmp_path / "zones.json"
    file_path.write_text("{}")

    def fake_config_path(hass, *parts):
        return str(file_path)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.zone_registry.config_path",
        fake_config_path,
    )

    assert add_zone("3", ["x"], ["p3"])
    zones = load_zones()
    assert zones["3"].plant_ids == ["p3"]

    assert attach_plants("3", ["p4", "p5"])
    assert sorted(load_zones()["3"].plant_ids) == ["p3", "p4", "p5"]

    assert detach_plants("3", ["p4"])
    assert load_zones()["3"].plant_ids == ["p3", "p5"]

    assert attach_solenoids("3", ["y"])
    assert load_zones()["3"].solenoids == ["x", "y"]

    assert detach_solenoids("3", ["x"])
    assert load_zones()["3"].solenoids == ["y"]

