"""Offline-first sync helpers shared by the edge add-on and cloud services."""

from .events import SyncEvent, VectorClock, decode_ndjson, encode_ndjson
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker
from .resolver_service import EdgeResolverService
from .conflict import ConflictResolver, ConflictPolicy

__all__ = [
    "SyncEvent",
    "VectorClock",
    "EdgeSyncStore",
    "EdgeSyncWorker",
    "EdgeResolverService",
    "ConflictResolver",
    "ConflictPolicy",
    "encode_ndjson",
    "decode_ndjson",
]
