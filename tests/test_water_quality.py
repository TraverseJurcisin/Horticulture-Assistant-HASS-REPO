from plant_engine import water_quality


def test_list_analytes():
    analytes = water_quality.list_analytes()
    assert "Na" in analytes
    assert "Cl" in analytes


def test_get_threshold():
    assert water_quality.get_threshold("Na") == 50
    assert water_quality.get_threshold("Unknown") is None


def test_interpret_water_profile():
    baseline, warnings = water_quality.interpret_water_profile({"Na": 60, "Cl": 50})
    assert baseline["Na"] == 60
    assert "Na" in warnings
    assert warnings["Na"]["limit"] == 50
    assert "Cl" not in warnings


def test_classify_water_quality():
    rating_good = water_quality.classify_water_quality({"Na": 40})
    assert rating_good == "good"
    rating_fair = water_quality.classify_water_quality({"Na": 60, "Cl": 80})
    assert rating_fair == "fair"
    rating_poor = water_quality.classify_water_quality({"Na": 60, "Cl": 120, "B": 2.0})
    assert rating_poor == "poor"
