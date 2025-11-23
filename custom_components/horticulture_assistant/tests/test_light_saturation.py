from ..engine.plant_engine.environment_manager import calculate_dli
from ..engine.plant_engine.light_saturation import (
    get_saturation_ppfd,
    list_supported_plants,
    recommend_supplemental_hours,
)


def test_get_saturation_ppfd():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert get_saturation_ppfd("tomato") == 900
    assert get_saturation_ppfd("unknown") is None


def test_recommend_supplemental_hours():
    # Tomato saturation 900 ppfd with 12h photoperiod
    current_ppfd = 500
    photoperiod = 12
    hours = recommend_supplemental_hours("tomato", current_ppfd, photoperiod)
    target_dli = calculate_dli(900, photoperiod)
    current_dli = calculate_dli(current_ppfd, photoperiod)
    remaining = target_dli - current_dli
    expected = round(remaining * 1_000_000 / (900 * 3600), 2)
    assert hours == expected

    # Already at saturation
    assert recommend_supplemental_hours("tomato", 900, 12) == 0.0

    # Invalid input returns None
    assert recommend_supplemental_hours("unknown", 500, 12) is None
    assert recommend_supplemental_hours("tomato", -1, 12) is None
    assert recommend_supplemental_hours("tomato", 500, 0) is None
