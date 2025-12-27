"""
Blender material extraction for RealityKit export.

Compatibility shim; implementation lives in Plugin/export/materials/extract/core.py.
"""

from .materials.extract.core import (
    extract_blender_material_data,
    collect_material_warnings,
)

__all__ = [
    "extract_blender_material_data",
    "collect_material_warnings",
]
