import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("aiohttp", reason="requires Home Assistant runtime")
pytest.importorskip("homeassistant.helpers", reason="requires Home Assistant runtime")

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("FERTILIZER_DATASET_INDEX_DIR", str(ROOT / "feature/fertilizer_dataset_sharded/index_sharded"))
os.environ.setdefault("FERTILIZER_DATASET_DETAIL_DIR", str(ROOT / "feature/fertilizer_dataset_sharded/detail"))

SCRIPT = ROOT / "scripts/fertilizer_search.py"


def test_search_cli(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "EARTH-CARE", "--limit", "1"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines
    assert any("EARTH-CARE" in line for line in lines)


def test_number_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "(#4083-0001)", "--number"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "N" in out and "K" in out
