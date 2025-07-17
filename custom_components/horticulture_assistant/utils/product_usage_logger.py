import uuid
from datetime import datetime
from typing import Dict, Any, Optional


def log_product_usage(
    product_id: str,
    batch_id: str,
    zone_ids: list,
    volume_liters: float,
    application_time: Optional[str] = None,
    recipe_id: Optional[str] = None,
    user_notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Creates a structured usage log record for a fertilizer product.

    Args:
        product_id: internal UUID of the fertilizer product
        batch_id: internal UUID of the batch it was added to
        zone_ids: list of zones this batch was applied to
        volume_liters: amount used in liters (or converted equivalent)
        application_time: ISO 8601 timestamp (optional, defaults to now)
        recipe_id: optional reference to the recipe used
        user_notes: any user-entered text
        metadata: optional dict of advanced metadata (e.g., EC, pH, density)

    Returns:
        Dictionary representing the log record
    """
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