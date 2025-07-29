from plant_engine.datasets import (
    list_datasets,
    get_dataset_description,
    search_datasets,
    list_datasets_by_category,
)
import plant_engine.datasets as datasets


def test_list_datasets_contains_known():
    datasets = list_datasets()
    assert "nutrient_guidelines.json" in datasets
    assert "irrigation_intervals.json" in datasets
    assert "soil_moisture_guidelines.json" in datasets
    assert "leaf_temperature_guidelines.json" in datasets
    assert "disease_monitoring_intervals.json" in datasets
    assert "reference_et0.json" in datasets
    assert "pesticide_modes.json" in datasets
    assert "frost_dates.json" in datasets
    assert "dataset_catalog.json" not in datasets


def test_list_datasets_includes_subdirectory():
    datasets = list_datasets()
    assert "fertilizers/fertilizer_products.json" in datasets


def test_get_dataset_description():
    desc = get_dataset_description("nutrient_guidelines.json")
    assert "macronutrient" in desc

    desc2 = get_dataset_description("micronutrient_guidelines.json")
    assert "micronutrient" in desc2

    desc3 = get_dataset_description("fertilizer_purity.json")
    assert "purity" in desc3

    desc4 = get_dataset_description("irrigation_intervals.json")
    assert "irrigation" in desc4

    desc5 = get_dataset_description("feature/wsda_refactored_sharded/index_sharded/")
    assert "WSDA" in desc5

    desc6 = get_dataset_description("soil_moisture_guidelines.json")
    assert "moisture" in desc6

    desc7 = get_dataset_description("disease_monitoring_intervals.json")
    assert "disease" in desc7

    desc8 = get_dataset_description("reference_et0.json")
    assert "ET0" in desc8 or "et0" in desc8.lower()
    desc9 = get_dataset_description("leaf_temperature_guidelines.json")
    assert "temperature" in desc9

    desc9 = get_dataset_description("pesticide_modes.json")
    assert "action" in desc9
    desc10 = get_dataset_description("frost_dates.json")
    assert "frost" in desc10


def test_search_datasets():
    results = search_datasets("irrigation")
    assert "irrigation_guidelines.json" in results
    assert "irrigation_intervals.json" in results
    assert all(
        "irrigation" in name or "irrigation" in desc.lower()
        for name, desc in results.items()
    )

    empty = search_datasets("does-not-exist")
    assert empty == {}


def test_list_datasets_by_category():
    cats = list_datasets_by_category()
    assert "fertilizers" in cats
    assert "fertilizers/fertilizer_products.json" in cats["fertilizers"]
    assert "nutrient_guidelines.json" in cats["root"]


def test_list_dataset_info_by_category():
    info = datasets.list_dataset_info_by_category()
    assert "fertilizers" in info
    fert = info["fertilizers"]
    assert "fertilizers/fertilizer_products.json" in fert
    root_info = info["root"]
    assert "nutrient_guidelines.json" in root_info
    assert isinstance(root_info["nutrient_guidelines.json"], str)


def test_catalog_custom_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.json").write_text("{}")
    (data_dir / "dataset_catalog.json").write_text('{"a.json": "A file"}')
    cat = datasets.DatasetCatalog(base_dir=data_dir)
    assert cat.list_datasets() == ["a.json"]
    assert cat.get_description("a.json") == "A file"
    assert cat.list_info()["a.json"] == "A file"
    assert cat.search("file") == {"a.json": "A file"}
    assert cat.list_by_category() == {"root": ["a.json"]}


def test_catalog_refresh(tmp_path):
    (tmp_path / "x.json").write_text("{}")
    cat = datasets.DatasetCatalog(base_dir=tmp_path)
    assert cat.list_datasets() == ["x.json"]
    (tmp_path / "y.json").write_text("{}")
    assert cat.list_datasets() == ["x.json"]
    cat.refresh()
    assert sorted(cat.list_datasets()) == ["x.json", "y.json"]


def test_catalog_overlay_priority(monkeypatch, tmp_path):
    base = tmp_path / "data"
    overlay = tmp_path / "overlay"
    base.mkdir()
    overlay.mkdir()
    (base / "a.json").write_text("{}")
    (overlay / "a.json").write_text('{"x": 1}')

    cat = datasets.DatasetCatalog(base_dir=base, overlay_dir=overlay)

    # Only one dataset should be returned
    assert cat.list_datasets() == ["a.json"]
    # Path resolution prefers overlay directory
    assert cat.find_path("a.json") == overlay / "a.json"


def test_catalog_paths_cached(tmp_path):
    base = tmp_path / "data"
    extra = tmp_path / "extra"
    overlay = tmp_path / "overlay"
    base.mkdir()
    extra.mkdir()
    overlay.mkdir()

    cat = datasets.DatasetCatalog(
        base_dir=base, extra_dirs=(extra,), overlay_dir=overlay
    )

    first = cat.paths()
    second = cat.paths()
    assert first is second
    assert first[0] == overlay
    assert base in first and extra in first


def test_get_dataset_path_and_load():
    path = datasets.get_dataset_path("nutrient_guidelines.json")
    assert path and path.exists()
    data = datasets.load_dataset_file("nutrient_guidelines.json")
    assert isinstance(data, dict)

def test_dataset_exists():
    assert datasets.dataset_exists("nutrient_guidelines.json")
    assert not datasets.dataset_exists("missing_dataset.json")
