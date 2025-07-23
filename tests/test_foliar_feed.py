from plant_engine.fertigation import get_foliar_guidelines, recommend_foliar_feed


def test_get_foliar_guidelines():
    data = get_foliar_guidelines("tomato", "vegetative")
    assert data == {"N": 300, "K": 400}


def test_recommend_foliar_feed():
    sched = recommend_foliar_feed("tomato", "vegetative", 1.0, purity={"N": 1.0, "K": 1.0})
    assert sched["N"] == 0.3
    assert sched["K"] == 0.4
