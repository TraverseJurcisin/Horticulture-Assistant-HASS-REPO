import importlib
import json

from ..engine.plant_engine import utils as utils


def test_load_dataset_df_dict(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.json").write_text(json.dumps({"a": {"x": 1}, "b": {"x": 2}}))
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    df = utils.load_dataset_df("sample.json")
    assert list(df.index) == ["a", "b"]
    assert list(df.columns) == ["x"]


def test_load_dataset_df_list(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.json").write_text(json.dumps([{"a": 1}, {"a": 2}]))
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    df = utils.load_dataset_df("sample.json")
    assert df.shape == (2, 1)


def test_load_dataset_df_csv(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "sample.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n")
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    df = utils.load_dataset_df("sample.csv")
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (2, 2)
