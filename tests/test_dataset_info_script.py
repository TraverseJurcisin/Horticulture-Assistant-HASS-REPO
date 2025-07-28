from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/dataset_info.py"


def test_list_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert "nutrient_guidelines.json" in lines


def test_search_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "search", "nutrient"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "nutrient_guidelines.json" in out


def test_categories_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "categories", "--describe"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "[fertilizers]" in out
    assert "fertilizers/fertilizer_products.json" in out
