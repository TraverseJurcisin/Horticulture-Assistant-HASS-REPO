from plant_engine.pruning_manager import (
    list_supported_plants,
    list_stages,
    get_pruning_instructions,
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
