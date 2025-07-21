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

search_products = wsda.search_products

def test_search_products():
    matches = search_products("earth-care", limit=2)
    assert any("EARTH-CARE" in m.upper() for m in matches)
