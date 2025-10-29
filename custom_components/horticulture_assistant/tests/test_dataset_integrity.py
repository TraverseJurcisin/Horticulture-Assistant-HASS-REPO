"""Verify all bundled dataset files load without error."""

import pytest

from plant_engine.utils import list_dataset_files, load_dataset


@pytest.mark.parametrize("filename", list_dataset_files())
def test_dataset_files_parse(filename):
    """All dataset files should be valid JSON or YAML."""
    data = load_dataset(filename)
    assert data is not None
