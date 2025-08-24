from datetime import date

from plant_engine.pruning_manager import (
    get_pruning_instructions,
    get_pruning_interval,
    list_stages,
    list_supported_plants,
    next_pruning_date,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "citrus" in plants


def test_list_stages():
    stages = list_stages("tomato")
    assert "vegetative" in stages
    assert "fruiting" in stages


def test_get_pruning_instructions():
    instr = get_pruning_instructions("tomato", "vegetative")
    assert instr.startswith("Remove side shoots")
    assert get_pruning_instructions("unknown", "stage") == ""


def test_get_pruning_interval():
    assert get_pruning_interval("tomato", "vegetative") == 7
    assert get_pruning_interval("citrus", "dormant") == 30
    assert get_pruning_interval("unknown") is None


def test_next_pruning_date():
    last = date(2024, 1, 1)
    nxt = next_pruning_date("tomato", "fruiting", last)
    assert nxt == date(2024, 1, 15)
    assert next_pruning_date("unknown", None, last) is None
