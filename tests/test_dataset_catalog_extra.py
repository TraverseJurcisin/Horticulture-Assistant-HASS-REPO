import importlib
import json

import plant_engine.datasets as datasets


def test_dataset_catalog_environment_dirs(tmp_path, monkeypatch):
    base = tmp_path / "base"
    extra = tmp_path / "extra"
    overlay = tmp_path / "overlay"
    base.mkdir()
    extra.mkdir()
    overlay.mkdir()

    (base / "base.json").write_text("{}")
    (extra / "extra.json").write_text("{}")
    (overlay / "overlay.json").write_text("{}")

    (base / "dataset_catalog.json").write_text(json.dumps({"base.json": "b"}))
    (extra / "dataset_catalog.json").write_text(json.dumps({"extra.json": "e"}))
    (overlay / "dataset_catalog.json").write_text(json.dumps({"overlay.json": "o"}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_EXTRA_DATA_DIRS", str(extra))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))

    importlib.reload(datasets)

    names = datasets.list_datasets()
    assert set(names) == {"base.json", "extra.json", "overlay.json"}

    desc = datasets.get_dataset_description("overlay.json")
    assert desc == "o"

    # reset module to default paths so other tests are unaffected
    monkeypatch.delenv("HORTICULTURE_DATA_DIR", raising=False)
    monkeypatch.delenv("HORTICULTURE_EXTRA_DATA_DIRS", raising=False)
    monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR", raising=False)
    importlib.reload(datasets)
