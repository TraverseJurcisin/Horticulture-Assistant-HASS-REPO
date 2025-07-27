from custom_components.horticulture_assistant.utils.species_cation_exchange import (
    MediaBuffer,
    apply_species_demand,
    recommend_amendments,
)


def test_apply_species_demand():
    media = MediaBuffer(Ca=100, K=80, Mg=40, S=20)
    updated = apply_species_demand(media, "citrus", days=2, base_daily_use=5)
    assert updated.Ca < media.Ca
    assert updated.K < media.K
    assert updated.Mg == media.Mg


def test_recommend_amendments_iris():
    media = MediaBuffer(Ca=50, K=50, Mg=2, S=10)
    msgs = recommend_amendments(media, "Iris", {"Mg": 5})
    assert any("MgSO" in m for m in msgs)


def test_recommend_amendments_iris_ratio():
    media = MediaBuffer(Ca=50, K=50, Mg=6, S=10)
    msgs = recommend_amendments(media, "iris", {"Mg": 5})
    assert any("S:Ca ratio" in m for m in msgs)
