import json
import zipfile
from pathlib import Path

import scripts.backup_profiles as bp


def _setup_sample(tmp_path: Path):
    plants = tmp_path / "plants"
    plants.mkdir()
    plant_file = plants / "sample.json"
    plant_file.write_text("{}")
    registry = tmp_path / "plant_registry.json"
    registry.write_text("{}")
    backup_dir = tmp_path / "backups"
    bp.configure_root(tmp_path)
    bp.DEFAULT_BACKUP_DIR = backup_dir
    return backup_dir, plant_file


def test_create_and_restore(tmp_path: Path):
    backup_dir, plant_file = _setup_sample(tmp_path)
    archive = bp.create_backup()
    assert archive.exists()
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert "plants/sample.json" in names
        assert "plant_registry.json" in names

    plant_file.write_text('{"changed":true}')
    bp.restore_backup(archive, output_dir=tmp_path)
    assert json.loads(plant_file.read_text()) == {}

    assert bp.verify_backup(archive)


def test_retention(tmp_path: Path):
    backup_dir, _ = _setup_sample(tmp_path)
    for _ in range(3):
        bp.create_backup(retain=2)
    archives = list(bp.list_backups())
    assert len(archives) == 2


def test_retention_zero(tmp_path: Path):
    _setup_sample(tmp_path)
    for _ in range(2):
        bp.create_backup()
    bp.create_backup(retain=0)
    assert list(bp.list_backups()) == []
