"""
Operators for RealityKit material validation and cleanup.
"""

import bpy
from bpy.types import Operator

from ..nodes import validate as rk_validate


def _get_active_material(context):
    """Resolve the active material from the current context."""
    if context.material:
        return context.material
    space = context.space_data
    if space and space.type == 'NODE_EDITOR' and space.tree_type == 'ShaderNodeTree':
        if getattr(space, "id", None) and hasattr(space.id, "node_tree"):
            return space.id
    obj = context.active_object
    if obj:
        return obj.active_material
    return None


class BLENDERTORCP_OT_validate_material(Operator):
    """Validate the active material against RealityKit rules."""
    bl_idname = "blendertorcp.validate_material"
    bl_label = "Validate RealityKit Material"
    bl_options = {'REGISTER'}

    def execute(self, context):
        material = _get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material to validate")
            return {'CANCELLED'}

        try:
            result = rk_validate.validate_material(material, strict=True)
        except TypeError:
            result = rk_validate.validate_material(material)
            if result.get("warnings"):
                result["errors"].extend(result["warnings"])
                result["warnings"] = []
            result["ok"] = not result["errors"]
        if result["errors"]:
            self.report({'ERROR'}, f"{len(result['errors'])} errors found in '{material.name}'")
            return {'FINISHED'}
        if result["warnings"]:
            self.report({'WARNING'}, f"{len(result['warnings'])} warnings found in '{material.name}'")
            return {'FINISHED'}

        self.report({'INFO'}, f"'{material.name}' is RealityKit-compatible")
        return {'FINISHED'}


class BLENDERTORCP_OT_select_offenders(Operator):
    """Select offending nodes in the active material."""
    bl_idname = "blendertorcp.select_offending_nodes"
    bl_label = "Select Offending Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        material = _get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material to inspect")
            return {'CANCELLED'}

        try:
            result = rk_validate.validate_material(material, strict=True)
        except TypeError:
            result = rk_validate.validate_material(material)
            if result.get("warnings"):
                result["errors"].extend(result["warnings"])
                result["warnings"] = []
            result["ok"] = not result["errors"]
        if not result["offending_nodes"]:
            self.report({'INFO'}, "No offending nodes found")
            return {'FINISHED'}

        rk_validate.select_offending_nodes(material, result)
        return {'FINISHED'}


class BLENDERTORCP_OT_remove_offenders(Operator):
    """Remove offending nodes from the active material."""
    bl_idname = "blendertorcp.remove_offending_nodes"
    bl_label = "Remove Offending Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        material = _get_active_material(context)
        if not material:
            self.report({'WARNING'}, "No active material to inspect")
            return {'CANCELLED'}

        try:
            result = rk_validate.validate_material(material, strict=True)
        except TypeError:
            result = rk_validate.validate_material(material)
            if result.get("warnings"):
                result["errors"].extend(result["warnings"])
                result["warnings"] = []
            result["ok"] = not result["errors"]
        removed = rk_validate.remove_offending_nodes(material, result)
        if removed == 0:
            self.report({'INFO'}, "No offending nodes to remove")
            return {'FINISHED'}

        self.report({'INFO'}, f"Removed {removed} offending nodes")
        return {'FINISHED'}


def register():
    """Register validation operators."""
    bpy.utils.register_class(BLENDERTORCP_OT_validate_material)
    bpy.utils.register_class(BLENDERTORCP_OT_select_offenders)
    bpy.utils.register_class(BLENDERTORCP_OT_remove_offenders)


def unregister():
    """Unregister validation operators."""
    bpy.utils.unregister_class(BLENDERTORCP_OT_remove_offenders)
    bpy.utils.unregister_class(BLENDERTORCP_OT_select_offenders)
    bpy.utils.unregister_class(BLENDERTORCP_OT_validate_material)
