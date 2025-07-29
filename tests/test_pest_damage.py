import builtins

from plant_engine import pest_monitor


def test_get_damage_threshold():
    assert pest_monitor.get_damage_threshold("aphids") == 20
    assert pest_monitor.get_damage_threshold("unknown") is None


def test_is_damage_severe():
    assert pest_monitor.is_damage_severe("aphids", 25) is True
    assert pest_monitor.is_damage_severe("aphids", 15) is False
    assert pest_monitor.is_damage_severe("unknown", 10) is None


def test_is_damage_severe_invalid():
    try:
        pest_monitor.is_damage_severe("aphids", -1)
    except ValueError:
        pass
    else:
        assert False, "Expected ValueError"
