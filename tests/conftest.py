import sys
import os
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("WSDA_INDEX_DIR", str(ROOT / "feature/wsda_refactored_sharded/index_sharded"))
os.environ.setdefault("WSDA_DETAIL_DIR", str(ROOT / "feature/wsda_refactored_sharded/detail"))
