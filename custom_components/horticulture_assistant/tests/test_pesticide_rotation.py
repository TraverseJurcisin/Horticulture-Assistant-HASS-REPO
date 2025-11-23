from ..engine.plant_engine.pesticide_manager import recommend_rotation_products


def test_rotation_for_known_pest():
    assert recommend_rotation_products("aphids") == ["imidacloprid", "pyrethrin"]


def test_rotation_unknown_pest():
    assert recommend_rotation_products("unknown") == []


def test_rotation_count_limit():
    res = recommend_rotation_products("aphids", count=1)
    assert res == ["imidacloprid"]
