from plant_engine.disease_manager import (
    get_disease_guidelines,
    get_disease_resistance,
    get_fungicide_options,
    list_known_diseases,
    recommend_fungicides,
    recommend_treatments,
)


def test_get_disease_guidelines():
    guide = get_disease_guidelines("citrus")
    assert "root rot" in guide
    assert guide["citrus greening"].startswith("Remove infected")


def test_get_disease_guidelines_case_insensitive():
    guide = get_disease_guidelines("CiTrUs")
    assert "root rot" in guide


def test_recommend_treatments():
    actions = recommend_treatments("citrus", ["root rot", "unknown"])
    assert actions["root rot"].startswith("Ensure good drainage")
    assert actions["unknown"] == "No guideline available"


def test_list_known_diseases():
    diseases = list_known_diseases("citrus")
    assert "root rot" in diseases


def test_get_disease_resistance():
    assert get_disease_resistance("citrus", "greasy_spot") == 4.0
    assert get_disease_resistance("citrus", "unknown") is None


def test_get_fungicide_options():
    opts = get_fungicide_options("blight")
    assert "copper fungicide" in opts
    assert "bacillus subtilis" in opts


def test_recommend_fungicides():
    recs = recommend_fungicides(["powdery mildew", "unknown"])
    assert recs["powdery mildew"] == [
        "sulfur spray",
        "potassium bicarbonate",
    ]
    assert recs["unknown"] == []


def test_get_fungicide_application_rate():
    from plant_engine.disease_manager import get_fungicide_application_rate

    assert get_fungicide_application_rate("copper fungicide") == 2.0
    assert get_fungicide_application_rate("unknown") is None


def test_calculate_fungicide_mix():
    from plant_engine.disease_manager import calculate_fungicide_mix

    mix = calculate_fungicide_mix("blight", 10)
    assert mix == {"copper fungicide": 20.0, "bacillus subtilis": 10.0}
