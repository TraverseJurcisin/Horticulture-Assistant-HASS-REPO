from plant_engine.biological_clock import (
    list_supported_plants,
    get_clock_reset_info,
    check_clock_reset,
    format_reset_message,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "iris" in plants


def test_get_clock_reset_info():
    info = get_clock_reset_info("iris")
    assert info["chilling_hours"] == 800


def test_check_clock_reset_true():
    assert check_clock_reset("iris", chilling_hours=800, photoperiod_hours=11)


def test_check_clock_reset_false():
    assert not check_clock_reset("iris", chilling_hours=500, photoperiod_hours=11)


def test_format_reset_message():
    msg = format_reset_message("Iris", "iris", chilling_hours=800, photoperiod_hours=11)
    assert "Iris" in msg
    assert "spring emergence" in msg
