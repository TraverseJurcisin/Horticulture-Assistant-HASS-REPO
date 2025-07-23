from plant_engine.utils import normalize_key


def test_normalize_key_lowercase():
    assert normalize_key("Hello") == "hello"


def test_normalize_key_spaces_replaced():
    assert normalize_key("My Plant") == "my_plant"


def test_normalize_key_non_string():
    assert normalize_key(123) == "123"
