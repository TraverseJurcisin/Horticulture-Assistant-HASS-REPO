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


def test_score_water_quality():
    assert water_quality.score_water_quality({"Na": 40}) == 100.0
    # Exceeding by 20% deducts 5 points
    score = water_quality.score_water_quality({"Na": 60})
    assert 94.0 <= score <= 95.0
    low_score = water_quality.score_water_quality({"Na": 120, "Cl": 120})
    assert low_score < score


def test_recommend_treatments():
    recs = water_quality.recommend_treatments({"Na": 60, "Cl": 50})
    assert "Na" in recs
    assert "Cl" not in recs


def test_summarize_water_profile():
    summary = water_quality.summarize_water_profile({"Na": 60, "Cl": 50})
    assert summary.rating == "fair"
    assert summary.baseline["Na"] == 60
    assert "Na" in summary.warnings
    assert summary.score < 100


def test_blend_water_profiles():
    from plant_engine import water_quality

    a = {"Na": 80, "Cl": 80}
    b = {"Na": 20, "Cl": 20}
    blend = water_quality.blend_water_profiles(a, b, 0.5)
    assert blend["Na"] == 50
    assert blend["Cl"] == 50


def test_max_safe_blend_ratio():
    from plant_engine import water_quality

    a = {"Na": 80, "Cl": 80}
    b = {"Na": 20, "Cl": 20}
    ratio = water_quality.max_safe_blend_ratio(a, b)
    assert 0.49 <= ratio <= 0.51


def test_salinity_limits():
    plants = water_quality.list_salinity_plants()
    assert "tomato" in plants
    limit = water_quality.get_salinity_limit("tomato")
    assert limit == 1.5
    assert water_quality.get_salinity_limit("unknown") is None
