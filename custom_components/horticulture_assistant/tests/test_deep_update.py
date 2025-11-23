from ..engine.plant_engine.utils import deep_update


def test_deep_update_nested_dict():
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    other = {"a": {"b": 4}, "e": 5}
    result = deep_update(base, other)
    assert result == {"a": {"b": 4, "c": 2}, "d": 3, "e": 5}


def test_deep_update_overwrite_non_mapping():
    base = {"a": {"b": 1}, "d": 2}
    other = {"a": 3}
    result = deep_update(base, other)
    assert result == {"a": 3, "d": 2}
