from plant_engine import bioinoculant_manager as bio


def test_list_supported_plants():
    plants = bio.list_supported_plants()
    assert "tomato" in plants


def test_get_recommended_inoculants():
    rec = bio.get_recommended_inoculants("tomato")
    assert "Trichoderma harzianum" in rec
    assert bio.get_recommended_inoculants("unknown") == []
