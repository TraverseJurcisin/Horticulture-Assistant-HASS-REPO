"""Offline-first sync helpers shared by the edge add-on and cloud services."""

from .auth import CloudAuthClient, CloudAuthError, CloudAuthTokens, CloudOrganization
from .conflict import ConflictPolicy, ConflictResolver
from .edge_store import EdgeSyncStore
from .edge_worker import EdgeSyncWorker
from .events import SyncEvent, VectorClock, decode_ndjson, encode_ndjson
from .manager import CloudSyncConfig, CloudSyncManager
from .resolver_service import (
    EdgeResolverService,
    ResolveAnnotations,
    ResolveResult,
    resolve_result_to_annotation,
    resolve_result_to_resolved_target,
)

__all__ = [
    "CloudAuthClient",
    "CloudAuthError",
    "CloudAuthTokens",
    "CloudOrganization",
    "SyncEvent",
    "VectorClock",
    "EdgeSyncStore",
    "EdgeSyncWorker",
    "EdgeResolverService",
    "ResolveResult",
    "ResolveAnnotations",
    "resolve_result_to_annotation",
    "resolve_result_to_resolved_target",
    "ConflictPolicy",
    "ConflictResolver",
    "encode_ndjson",
    "decode_ndjson",
    "CloudSyncManager",
    "CloudSyncConfig",
]
