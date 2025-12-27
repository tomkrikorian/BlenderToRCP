"""
RealityKit node catalog, group builders, and validation utilities.
"""

_needs_reload = "bpy" in locals()

import bpy

from . import metadata
from . import nodegroups
from . import validate
from . import handlers

if _needs_reload:
    import importlib
    metadata = importlib.reload(metadata)
    nodegroups = importlib.reload(nodegroups)
    validate = importlib.reload(validate)
    handlers = importlib.reload(handlers)

__all__ = [
    "metadata",
    "nodegroups",
    "validate",
    "handlers",
]
