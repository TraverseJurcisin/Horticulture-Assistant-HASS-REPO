import importlib
import os
import plant_engine.utils as utils


def test_dataset_paths_env(monkeypatch, tmp_path):
    base = tmp_path / "data"
    extra = tmp_path / "extra"
    base.mkdir()
    extra.mkdir()
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_EXTRA_DATA_DIRS", str(extra))
    importlib.reload(utils)
    paths = utils.dataset_paths()
    assert paths[0] == base
    assert extra in paths
    utils.clear_dataset_cache()


def test_clear_dataset_cache_resets_paths(monkeypatch, tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    importlib.reload(utils)
    paths1 = utils.dataset_paths()
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(tmp_path / "other"))
    utils.clear_dataset_cache()
    importlib.reload(utils)
    paths2 = utils.dataset_paths()
    assert paths1 != paths2
    utils.clear_dataset_cache()

