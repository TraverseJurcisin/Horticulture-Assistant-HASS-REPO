import importlib.util
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data/fertilizers"
os.environ.setdefault("FERTILIZER_DATASET_INDEX_DIR", str(DATA_DIR / "index_sharded"))
os.environ.setdefault("FERTILIZER_DATASET_DETAIL_DIR", str(DATA_DIR / "detail"))

PACKAGE_DIR = ROOT / "engine/plant_engine"


def _ensure_package(name: str, path: Path) -> None:
    if name in sys.modules:
        module = sys.modules[name]
        module.__path__ = [str(path)]  # type: ignore[attr-defined]
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


_ensure_package("custom_components", ROOT.parent)
_ensure_package("custom_components.horticulture_assistant", ROOT)
_ensure_package("custom_components.horticulture_assistant.engine", ROOT / "engine")
_ensure_package("custom_components.horticulture_assistant.engine.plant_engine", PACKAGE_DIR)


def _load_module(module_name: str, file: Path):
    spec = importlib.util.spec_from_file_location(module_name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fertilizer_dataset_loader = _load_module(
    "custom_components.horticulture_assistant.engine.plant_engine.fertilizer_dataset_loader",
    PACKAGE_DIR / "fertilizer_dataset_loader.py",
)
dataset_lookup = _load_module(
    "custom_components.horticulture_assistant.engine.plant_engine.fertilizer_dataset_lookup",
    PACKAGE_DIR / "fertilizer_dataset_lookup.py",
)

get_product_npk_by_name = dataset_lookup.get_product_npk_by_name
get_product_npk_by_number = dataset_lookup.get_product_npk_by_number
get_product_analysis_by_name = dataset_lookup.get_product_analysis_by_name
get_product_analysis_by_number = dataset_lookup.get_product_analysis_by_number
search_products = dataset_lookup.search_products
list_product_names = dataset_lookup.list_product_names
list_product_numbers = dataset_lookup.list_product_numbers
recommend_products_for_nutrient = dataset_lookup.recommend_products_for_nutrient


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


def test_recommend_products_for_nutrient():
    top = recommend_products_for_nutrient("K", limit=3)
    assert len(top) == 3
    first = get_product_analysis_by_name(top[0]).get("K")
    second = get_product_analysis_by_name(top[1]).get("K")
    assert first >= second
