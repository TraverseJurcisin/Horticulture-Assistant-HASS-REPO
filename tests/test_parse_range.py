import pytest
from plant_engine.utils import parse_range

def test_parse_range_valid_list():
    assert parse_range([1, 2]) == (1.0, 2.0)


def test_parse_range_tuple():
    assert parse_range(("3", 4)) == (3.0, 4.0)


def test_parse_range_invalid():
    assert parse_range([1]) is None
    assert parse_range("bad") is None
