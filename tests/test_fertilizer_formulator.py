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
calculate_fertilizer_nutrients_from_mass = fert_mod.calculate_fertilizer_nutrients_from_mass
calculate_fertilizer_cost_from_mass = fert_mod.calculate_fertilizer_cost_from_mass
estimate_mix_cost = fert_mod.estimate_mix_cost
estimate_cost_breakdown = fert_mod.estimate_cost_breakdown
find_products = fert_mod.find_products
calculate_mix_nutrients = fert_mod.calculate_mix_nutrients
calculate_mix_ppm = fert_mod.calculate_mix_ppm
calculate_mix_density = fert_mod.calculate_mix_density
check_solubility_limits = fert_mod.check_solubility_limits
estimate_cost_per_nutrient = fert_mod.estimate_cost_per_nutrient


def test_convert_guaranteed_analysis():
    ga = {"N": 0.05, "P2O5": 0.1, "K2O": 0.2}
    result = convert_guaranteed_analysis(ga)
    assert result["N"] == 0.05
    assert round(result["P"], 4) == 0.0436
    assert round(result["K"], 3) == 0.166


def test_convert_guaranteed_analysis_skips_none():
    ga = {"N": 0.1, "B": None}
    result = convert_guaranteed_analysis(ga)
    assert result["N"] == 0.1
    assert "B" not in result


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


def test_mass_helpers_match_volume_equivalents():
    mass = 9.6  # grams corresponding to 10 mL at 0.96 kg/L
    grams_output = calculate_fertilizer_nutrients_from_mass("foxfarm_grow_big", mass)
    volume_output = calculate_fertilizer_nutrients(
        "plant", "foxfarm_grow_big", 10
    )["nutrients"]
    assert grams_output == volume_output

    cost_mass = calculate_fertilizer_cost_from_mass("foxfarm_grow_big", mass)
    cost_volume = calculate_fertilizer_cost("foxfarm_grow_big", 10)
    assert cost_mass == cost_volume

    with pytest.raises(ValueError):
        calculate_fertilizer_nutrients_from_mass("foxfarm_grow_big", 0)
    with pytest.raises(ValueError):
        calculate_fertilizer_cost_from_mass("foxfarm_grow_big", -1)
    with pytest.raises(KeyError):
        calculate_fertilizer_cost_from_mass("unknown", 10)


def test_estimate_mix_cost():
    mix = {"foxfarm_grow_big": 20}
    cost = estimate_mix_cost(mix)
    assert round(cost, 2) == 0.42
    with pytest.raises(KeyError):
        estimate_mix_cost({"unknown": 10})


def test_estimate_cost_breakdown():
    mix = {"foxfarm_grow_big": 20}
    breakdown = estimate_cost_breakdown(mix)
    assert breakdown["N"] > 0
    assert round(sum(breakdown.values()), 2) == 0.41


def test_find_products_matches_id_and_name():
    assert "foxfarm_grow_big" in find_products("grow big")
    assert "foxfarm_grow_big" in find_products("foxfarm_grow_big")


def test_list_products_sorted_by_name():
    ids = list_products()
    names = [get_product_info(pid).product_name or pid for pid in ids]
    assert names == sorted(names)


def test_calculate_mix_nutrients():
    mix = {"foxfarm_grow_big": 9.6}
    totals = calculate_mix_nutrients(mix)

    reference = calculate_fertilizer_nutrients(
        "plant", "foxfarm_grow_big", 10
    )["nutrients"]

    assert totals == reference


def test_calculate_mix_ppm():
    mix = {"foxfarm_grow_big": 9.6}
    ppm = calculate_mix_ppm(mix, 10)

    reference = calculate_mix_nutrients(mix)
    expected = {k: round(v / 10, 2) for k, v in reference.items()}

    assert ppm == expected

    with pytest.raises(ValueError):
        calculate_mix_ppm(mix, 0)


def test_calculate_mix_density():
    schedule = {"foxfarm_grow_big": 200, "magriculture": 100}
    density = calculate_mix_density(schedule)
    assert round(density, 3) == 0.973

    assert calculate_mix_density({}) == 0.0

    with pytest.raises(KeyError):
        calculate_mix_density({"unknown": 10})


def test_check_solubility_limits():
    schedule = {"foxfarm_grow_big": 400}
    warnings = check_solubility_limits(schedule, 1)
    assert warnings["foxfarm_grow_big"] > 0

    ok = check_solubility_limits({"foxfarm_grow_big": 100}, 1)
    assert ok == {}

    with pytest.raises(ValueError):
        check_solubility_limits(schedule, 0)


def test_estimate_cost_per_nutrient():
    costs = estimate_cost_per_nutrient("foxfarm_grow_big")
    assert "N" in costs and costs["N"] > 0
    # cost per nutrient should be higher for micro nutrients
    assert costs["N"] < costs.get("Fe", costs["N"])

    with pytest.raises(KeyError):
        estimate_cost_per_nutrient("unknown")

