from plant_engine.guidelines import get_guideline_summary


def test_get_guideline_summary():
    data = get_guideline_summary("citrus", "fruiting")
    assert data["environment"]["temp_c"] == [18, 28]
    assert data["nutrients"]["N"] == 120
    assert "aphids" in data["pest_guidelines"]
    assert "citrus greening" in data["disease_guidelines"]
    assert "citrus greening" in data["disease_prevention"]
    assert data["ph_range"] == [5.5, 6.5]
    assert data["stage_info"]["duration_days"] == 90
    assert data["micronutrients"] == {}
    assert data["pest_thresholds"]["aphids"] == 5
    assert "ladybugs" in data["beneficial_insects"]["aphids"]
    assert data["bioinoculants"] == []
    assert data["irrigation_volume_ml"] == 300
    assert "irrigation_interval_days" in data


def test_guideline_summary_no_stage():
    data = get_guideline_summary("citrus")
    assert "stages" in data and "vegetative" in data["stages"]

def test_guideline_summary_bioinoculants():
    data = get_guideline_summary("tomato", "fruiting")
    assert "Trichoderma harzianum" in data["bioinoculants"]

