from datetime import date

from plant_engine.fertigation import (
    get_foliar_guidelines,
    recommend_foliar_feed,
    get_foliar_feed_interval,
    next_foliar_feed_date,
)


def test_get_foliar_guidelines():
    data = get_foliar_guidelines("tomato", "vegetative")
    assert data == {"N": 300, "K": 400}


def test_recommend_foliar_feed():
    sched = recommend_foliar_feed("tomato", "vegetative", 1.0, purity={"N": 1.0, "K": 1.0})
    assert sched["N"] == 0.3
    assert sched["K"] == 0.4


def test_get_foliar_feed_interval():
    assert get_foliar_feed_interval("tomato", "vegetative") == 7
    assert get_foliar_feed_interval("lettuce") == 14
    assert get_foliar_feed_interval("unknown") is None


def test_next_foliar_feed_date():
    last = date(2023, 1, 1)
    expected = date(2023, 1, 8)
    assert next_foliar_feed_date("tomato", "vegetative", last) == expected
    assert next_foliar_feed_date("unknown", None, last) is None
