"""
MaterialX builder compatibility layer.

Keeps legacy imports working after splitting graph and extraction modules.
"""

from .materials.graph import MaterialXGraphBuilder
from .materials.extract.core import (
    extract_blender_material_data,
    collect_material_warnings,
)

__all__ = [
    "MaterialXGraphBuilder",
    "extract_blender_material_data",
    "collect_material_warnings",
]
