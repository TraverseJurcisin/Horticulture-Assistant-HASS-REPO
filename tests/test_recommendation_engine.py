from custom_components.horticulture_assistant.utils import recommendation_engine as re


def _setup_engine(auto=False):
    eng = re.RecommendationEngine()
    eng.set_auto_approve(auto)
    eng.update_plant_profile(
        "p1",
        {
            "n_required_ppm": 100,
            "min_vwc": 30,
            "zones": ["bed1"],
            "plant_type": "lettuce",
            "lifecycle_stage": "seedling",
        },
    )
    eng.update_sensor_data(
        "p1",
        {"nitrate_ppm": 20, "phosphate_ppm": 10, "potassium_ppm": 70, "vwc": 25},
    )
    eng.update_product_availability({"n_fert": {"elements": ["N"]}})
    eng.update_ai_feedback("p1", {"alerts": ["check drainage"]})
    eng.update_environment_data("p1", {"temp_c": 30, "humidity_pct": 40, "light_ppfd": 100})
    return eng


def test_recommendation_engine_requires_approval():
    eng = _setup_engine(auto=False)
    rec = eng.recommend("p1")
    assert rec.requires_approval is True
    assert rec.fertilizers[0].product_name == "n_fert"
    assert rec.fertilizers[0].reason == "N deficit"
    assert rec.fertilizers[0].severity == "severe"
    assert rec.irrigation.volume_liters == 0.05
    assert "check drainage" in rec.notes


def test_recommendation_engine_auto_approve():
    eng = _setup_engine(auto=True)
    rec = eng.recommend("p1")
    assert rec.requires_approval is False


def test_recommendation_engine_environment_notes():
    eng = _setup_engine(auto=False)
    rec = eng.recommend("p1")
    assert any("temperature" in n for n in rec.notes)


def test_recommendation_engine_recommend_all_and_reset():
    eng = _setup_engine(auto=False)
    all_recs = eng.recommend_all()
    assert "p1" in all_recs
    eng.reset_state()
    assert eng.plant_profiles == {}
    assert eng._element_map == {}


def test_fertilizer_recommendation_severity():
    eng = _setup_engine(auto=False)
    rec = eng.recommend("p1")
    fert = rec.fertilizers[0]
    assert fert.severity in {"mild", "moderate", "severe"}
