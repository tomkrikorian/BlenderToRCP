"""
MaterialX graph construction for RealityKit shaders.

Compatibility shim; implementation lives in Plugin/export/materials/graph.py.
"""

from .materials.graph import MaterialXGraphBuilder

__all__ = [
    "MaterialXGraphBuilder",
]
