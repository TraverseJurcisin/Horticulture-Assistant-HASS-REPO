from ..engine.plant_engine import bioinoculant_info as info


def test_list_inoculants():
    inoculants = info.list_inoculants()
    assert "Trichoderma harzianum" in inoculants
    assert "Bacillus subtilis" in inoculants


def test_get_inoculant_info():
    data = info.get_inoculant_info("Trichoderma harzianum")
    assert data.get("category") == "fungal"
    assert info.get_inoculant_info("unknown") == {}
