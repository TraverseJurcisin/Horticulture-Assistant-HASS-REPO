from plant_engine import crop_rotation


def test_rotation_lookups():
    plants = crop_rotation.list_supported_plants()
    assert "lettuce" in plants
    assert crop_rotation.get_rotation_interval("tomato") == 24
    assert crop_rotation.get_preceding_crops("lettuce")[0] == "beans"
    assert crop_rotation.get_rotation_interval("unknown") is None
