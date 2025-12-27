"""
Operator modules for BlenderToRCP.
"""

_needs_reload = "bpy" in locals()

import bpy

from . import export_operator
from . import bake_export_operator
from . import nodegroup_operators
from . import validation_operators

if _needs_reload:
    import importlib
    export_operator = importlib.reload(export_operator)
    bake_export_operator = importlib.reload(bake_export_operator)
    nodegroup_operators = importlib.reload(nodegroup_operators)
    validation_operators = importlib.reload(validation_operators)


def register():
    """Register all operator classes."""
    export_operator.register()
    bake_export_operator.register()
    nodegroup_operators.register()
    validation_operators.register()


def unregister():
    """Unregister all operator classes."""
    validation_operators.unregister()
    nodegroup_operators.unregister()
    bake_export_operator.unregister()
    export_operator.unregister()
