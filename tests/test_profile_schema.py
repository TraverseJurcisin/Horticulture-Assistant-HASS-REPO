import subprocess
import sys
from pathlib import Path


def test_profiles_validate():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "validate_profiles.py"
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"Profile validation failed:\n{proc.stdout}\n{proc.stderr}"


def test_logs_validate():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "validate_logs.py"
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"Log validation failed:\n{proc.stdout}\n{proc.stderr}"
