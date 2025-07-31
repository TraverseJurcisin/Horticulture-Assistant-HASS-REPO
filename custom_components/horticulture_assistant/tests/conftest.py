import sys
import os
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HA_PATH = ROOT / "custom_components" / "horticulture_assistant"
if str(HA_PATH) not in sys.path:
    sys.path.insert(0, str(HA_PATH))
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
