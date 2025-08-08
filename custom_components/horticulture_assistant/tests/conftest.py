import sys
import os
from pathlib import Path
import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("WSDA_INDEX_DIR", str(ROOT / "feature/wsda_refactored_sharded/index_sharded"))
os.environ.setdefault("WSDA_DETAIL_DIR", str(ROOT / "feature/wsda_refactored_sharded/detail"))

# Detect optional dataset availability. Many CLI and WSDA tests rely on
# large reference datasets that are not included in this trimmed repository.
HAS_LOCAL_DATA = (ROOT / "data" / "local").exists()
HAS_WSDA_DATA = Path(os.environ["WSDA_INDEX_DIR"]).exists()


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests that require missing datasets.

    Tests whose file name contains ``wsda`` expect the WSDA reference data to
    be present. Script-oriented tests or tests with ``dataset`` in their nodeid
    depend on local datasets. When these resources are absent we mark the
    corresponding tests as skipped to avoid noisy failures.
    """

    skip_local = pytest.mark.skip(reason="requires local datasets")
    skip_wsda = pytest.mark.skip(reason="requires WSDA dataset")

    for item in items:
        name = item.fspath.basename
        nodeid = item.nodeid
        if "wsda" in name.lower() and not HAS_WSDA_DATA:
            item.add_marker(skip_wsda)
        elif ("script" in name.lower() or "dataset" in nodeid) and not HAS_LOCAL_DATA:
            item.add_marker(skip_local)
