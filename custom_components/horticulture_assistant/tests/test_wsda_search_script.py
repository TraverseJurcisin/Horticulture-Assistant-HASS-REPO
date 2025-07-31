from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "WSDA_INDEX_DIR",
    str(
        ROOT / "custom_components/horticulture_assistant/data/fertilizers/index_sharded"
    ),
)
os.environ.setdefault(
    "WSDA_DETAIL_DIR",
    str(ROOT / "custom_components/horticulture_assistant/data/fertilizers/detail"),
)
SCRIPT_MODULE = "custom_components.horticulture_assistant.scripts.wsda_search"


def test_search_cli(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT),
            str(ROOT / "custom_components" / "horticulture_assistant"),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [sys.executable, "-m", SCRIPT_MODULE, "EARTH-CARE", "--limit", "1"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines
    assert any("EARTH-CARE" in line for line in lines)


def test_number_cli():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(ROOT),
            str(ROOT / "custom_components" / "horticulture_assistant"),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [sys.executable, "-m", SCRIPT_MODULE, "(#4083-0001)", "--number"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    out = result.stdout
    assert "N" in out and "K" in out
