import json
import os
from pathlib import Path

import pytest

from custom_components.horticulture_assistant.utils import plant_profile_loader as loader


def test_load_profile_from_json(tmp_path):
    data = {
        "general": {"plant_type": "test"},
        "thresholds": {"light": 100, "temperature": [20, 30], "EC": 1.2},
        "stages": {"seedling": {"stage_duration": 10}},
        "nutrients": {"N": 100}
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data))

    profile = loader.load_profile_from_path(path)
    assert profile["general"]["plant_type"] == "test"
    assert profile["thresholds"]["light"] == 100
    assert profile["stages"]["seedling"]["stage_duration"] == 10


def test_load_profile_from_yaml(tmp_path):
    yaml_content = """
    general:
      plant_type: tomato
    thresholds:
      light: 200
      temperature: [22, 30]
      EC: 2.0
    stages:
      seedling:
        stage_duration: 14
    """
    path = tmp_path / "tomato.yaml"
    path.write_text(yaml_content)

    profile = loader.load_profile_from_path(path)
    assert profile["general"]["plant_type"] == "tomato"
    assert profile["stages"]["seedling"]["stage_duration"] == 14


def test_load_profile_by_id_custom_dir(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    (plants / "plant1.json").write_text("{}")

    profile = loader.load_profile_by_id("plant1", base_dir=plants)
    assert profile == {"general": {}, "thresholds": {}, "stages": {}, "nutrients": {}}


def test_load_profile_missing(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    monkeypatch_dir = plants
    orig = loader.DEFAULT_BASE_DIR
    try:
        loader.DEFAULT_BASE_DIR = monkeypatch_dir
        profile = loader.load_profile_by_id("missing")
    finally:
        loader.DEFAULT_BASE_DIR = orig
    assert profile == {}
