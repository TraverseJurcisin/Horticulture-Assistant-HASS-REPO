"""Ensure manifest and config flow metadata are present."""

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def manifest():
    manifest_path = Path(__file__).parents[1] / "custom_components" / "horticulture_assistant" / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_manifest_config_flow_enabled(manifest):
    assert manifest.get("config_flow") is True


def test_manifest_has_version(manifest):
    version = manifest.get("version")
    assert isinstance(version, str) and version.strip(), "manifest version must be a non-empty string"


def test_config_flow_class_defined():
    module = importlib.import_module("custom_components.horticulture_assistant.config_flow")
    assert hasattr(module, "ConfigFlow"), "ConfigFlow class must be defined for UI setup"
