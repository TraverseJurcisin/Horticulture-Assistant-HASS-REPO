"""Engine subpackage for Horticulture Assistant.

An empty module previously prevented Python from treating this directory as
package after project restructuring.  Adding this file restores standard
package semantics so modules like ``push_to_approval_queue`` can be imported
using ``custom_components.horticulture_assistant.engine``.
"""
__all__ = []
