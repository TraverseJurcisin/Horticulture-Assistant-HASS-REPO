"""Offline-first sync helpers shared by the edge add-on and cloud services."""

from .events import SyncEvent, VectorClock, decode_ndjson, encode_ndjson
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker
from .resolver_service import (
    EdgeResolverService,
    ResolveAnnotations,
    ResolveResult,
    resolve_result_to_annotation,
    resolve_result_to_resolved_target,
)
from .conflict import ConflictResolver, ConflictPolicy

__all__ = [
    "SyncEvent",
    "VectorClock",
    "EdgeSyncStore",
    "EdgeSyncWorker",
    "EdgeResolverService",
    "ResolveResult",
    "ResolveAnnotations",
    "resolve_result_to_annotation",
    "resolve_result_to_resolved_target",
    "ConflictResolver",
    "ConflictPolicy",
    "encode_ndjson",
    "decode_ndjson",
]
