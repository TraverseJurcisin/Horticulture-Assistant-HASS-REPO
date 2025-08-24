"""Logging helpers for recording fertilizer application events."""

import uuid
from datetime import datetime
from typing import Any

__all__ = ["log_product_usage"]


def log_product_usage(
    product_id: str,
    batch_id: str,
    zone_ids: list,
    volume_liters: float,
    application_time: str | None = None,
    recipe_id: str | None = None,
    user_notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a structured usage log entry."""
    usage_record = {
        "usage_id": str(uuid.uuid4()),
        "product_id": product_id,
        "batch_id": batch_id,
        "zone_ids": zone_ids,
        "volume_liters": round(volume_liters, 4),
        "application_time": application_time or datetime.now().isoformat(),
        "recipe_id": recipe_id,
        "user_notes": user_notes or "",
        "metadata": metadata or {},
    }

    return usage_record
