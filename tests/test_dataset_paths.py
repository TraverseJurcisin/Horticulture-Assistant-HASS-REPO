import json

import plant_engine.utils as utils


def test_set_dataset_paths(tmp_path):
    base1 = tmp_path / "base1"
    base2 = tmp_path / "base2"
    overlay = tmp_path / "overlay"
    base1.mkdir()
    base2.mkdir()
    overlay.mkdir()

    (base1 / "sample.json").write_text(json.dumps({"a": 1}))
    (base2 / "sample.json").write_text(json.dumps({"a": 2, "b": 3}))
    (overlay / "sample.json").write_text(json.dumps({"c": 4}))

    utils.set_dataset_paths(data_dir=base1)
    assert utils.load_dataset("sample.json") == {"a": 1}

    utils.set_dataset_paths(data_dir=base2, overlay_dir=overlay, extra_dirs=[base1])
    result = utils.load_dataset("sample.json")
    # extra directories override the base data directory
    assert result == {"a": 1, "b": 3, "c": 4}

    # reset to defaults using None
    utils.set_dataset_paths(None)

