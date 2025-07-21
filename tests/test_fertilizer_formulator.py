import importlib.util
import sys
from pathlib import Path
import pytest

module_path = (
    Path(__file__).resolve().parents[1]
    / "custom_components/horticulture_assistant/fertilizer_formulator.py"
)
spec = importlib.util.spec_from_file_location("fertilizer_formulator", module_path)
fert_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fert_mod
spec.loader.exec_module(fert_mod)

calculate_fertilizer_nutrients = fert_mod.calculate_fertilizer_nutrients
convert_guaranteed_analysis = fert_mod.convert_guaranteed_analysis
list_products = fert_mod.list_products
get_product_info = fert_mod.get_product_info
calculate_fertilizer_cost = fert_mod.calculate_fertilizer_cost


def test_convert_guaranteed_analysis():
    ga = {"N": 0.05, "P2O5": 0.1, "K2O": 0.2}
    result = convert_guaranteed_analysis(ga)
    assert result["N"] == 0.05
    assert round(result["P"], 4) == 0.0436
    assert round(result["K"], 3) == 0.166


def test_calculate_fertilizer_nutrients():
    payload = calculate_fertilizer_nutrients("plant1", "foxfarm_grow_big", 10)
    nutrients = payload["nutrients"]
    assert round(nutrients["N"], 1) == 576.0
    assert round(nutrients["P"], 2) == 167.42
    assert round(nutrients["K"], 2) == 318.72


def test_list_products_contains_inventory():
    ids = list_products()
    assert "foxfarm_grow_big" in ids

    info = get_product_info("foxfarm_grow_big")
    assert round(info.density_kg_per_l, 2) == 0.96


def test_invalid_inputs():
    with pytest.raises(ValueError):
        calculate_fertilizer_nutrients("plant", "unknown", 10)
    with pytest.raises(ValueError):
        calculate_fertilizer_nutrients("plant", "foxfarm_grow_big", 0)
    with pytest.raises(KeyError):
        get_product_info("unknown")


def test_calculate_fertilizer_cost():
    cost = calculate_fertilizer_cost("foxfarm_grow_big", 10)
    assert round(cost, 2) == 0.2
    with pytest.raises(ValueError):
        calculate_fertilizer_cost("foxfarm_grow_big", -1)
    with pytest.raises(KeyError):
        calculate_fertilizer_cost("unknown", 10)
