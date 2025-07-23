import importlib.util
import sys
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "plant_engine/wsda_lookup.py"
spec = importlib.util.spec_from_file_location("wsda_lookup", module_path)
wsda = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wsda
spec.loader.exec_module(wsda)

get_product_npk_by_name = wsda.get_product_npk_by_name
get_product_npk_by_number = wsda.get_product_npk_by_number
get_product_analysis_by_name = wsda.get_product_analysis_by_name
get_product_analysis_by_number = wsda.get_product_analysis_by_number
search_products = wsda.search_products
list_product_names = wsda.list_product_names
list_product_numbers = wsda.list_product_numbers


def test_lookup_by_name():
    result = get_product_npk_by_name("1ST CHOICE FERTILIZER EARTH-CARE PLUS 5-6-6")
    assert result["N"] == 5.0
    assert result["P"] == 6.0
    assert result["K"] == 6.0


def test_lookup_by_number():
    result = get_product_npk_by_number("(#4083-0001)")
    assert result["N"] == 5.0
    assert result["P"] == 6.0
    assert result["K"] == 6.0


def test_full_analysis_lookup():
    by_name = get_product_analysis_by_name("1ST CHOICE FERTILIZER EARTH-CARE PLUS 5-6-6")
    by_number = get_product_analysis_by_number("(#4083-0001)")
    assert by_name["N"] == 5.0
    assert by_number["K"] == 6.0


def test_search_products():
    results = search_products("EARTH-CARE")
    assert any("EARTH-CARE" in name for name in results)


def test_lookup_unknown_product():
    assert get_product_npk_by_name("nonexistent") == {}
    assert get_product_npk_by_number("(#0000-0000)") == {}


def test_search_limit():
    results = search_products("CARE", limit=1)
    assert len(results) == 1


def test_list_product_names_contains_known():
    names = list_product_names()
    assert any("EARTH-CARE" in n for n in names)


def test_list_product_numbers_contains_known():
    numbers = list_product_numbers()
    assert "(#4083-0001)" in numbers
