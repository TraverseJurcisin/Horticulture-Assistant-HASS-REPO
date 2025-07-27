from plant_engine.utils import parse_range

def test_parse_range_valid_list():
    assert parse_range([1, 2]) == (1.0, 2.0)


def test_parse_range_tuple():
    assert parse_range(("3", 4)) == (3.0, 4.0)


def test_parse_range_invalid():
    assert parse_range([1]) is None
    assert parse_range("bad") is None


def test_parse_range_extra_items():
    assert parse_range([1, 2, 3]) == (1.0, 2.0)


def test_parse_range_iterable():
    assert parse_range(iter([4, "5", 6])) == (4.0, 5.0)


def test_parse_range_reversed_order():
    assert parse_range([5, 1]) == (1.0, 5.0)


def test_parse_range_non_finite():
    assert parse_range([float("inf"), 1]) is None
    assert parse_range([float("nan"), 2]) is None
