from plant_engine.companion_manager import (
    list_supported_plants,
    get_companion_info,
    recommend_companions,
    recommend_antagonists,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "cucumber" in plants


def test_get_companion_info():
    info = get_companion_info("tomato")
    assert info["companions"] == ["basil", "marigold"]
    assert "fennel" in info["antagonists"]


def test_recommend_companions():
    assert "basil" in recommend_companions("tomato")
    assert recommend_companions("unknown") == []


def test_recommend_antagonists():
    assert "sage" in recommend_antagonists("cucumber")
    assert recommend_antagonists("unknown") == []
