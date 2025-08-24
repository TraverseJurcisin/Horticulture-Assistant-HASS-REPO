from datetime import datetime


def is_expired(
    expiration_date: str | None,
    current_date: str | None = None,
) -> bool:
    """
    Check if a product is past its expiration date.

    Args:
        expiration_date: ISO format string (e.g. "2025-09-30")
        current_date: Optional override of today's date (ISO string)

    Returns:
        True if expired, False otherwise
    """
    if not expiration_date:
        return False  # No expiration means indefinite

    today = datetime.fromisoformat(current_date) if current_date else datetime.now()
    expires = datetime.fromisoformat(expiration_date)

    return today > expires


def should_warn_about_expiration(
    is_biological: bool,
    expiration_date: str | None,
    manufacture_date: str | None = None,
    temperature_sensitive: bool = False,
    storage_temp_c: float | None = None,
) -> bool:
    """
    Determine whether a product should raise a warning based on expiration risk.

    Args:
        is_biological: True if product is biologically derived
        expiration_date: string in ISO format (optional)
        manufacture_date: optional date of manufacture in ISO format
        temperature_sensitive: does the product degrade under temperature stress?
        storage_temp_c: most recent storage temp if available

    Returns:
        True if warning should be raised
    """
    expired = is_expired(expiration_date)
    if expired:
        return True

    if is_biological and not expiration_date:
        # Warn if biological with no expiration
        return True

    if temperature_sensitive and storage_temp_c is not None:
        if storage_temp_c > 35 or storage_temp_c < 0:
            return True  # too hot or frozen

    return False
