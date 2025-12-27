"""
MaterialX material authoring for USD stages.

Compatibility shim; implementation lives in Plugin/export/materials/.
"""

from .materials.author import create_materialx_material
from .materials.rewrite import rewrite_materials

__all__ = [
    "create_materialx_material",
    "rewrite_materials",
]
