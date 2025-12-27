"""
Shader Editor panel for RealityKit compatibility status.
"""

import bpy
from bpy.types import Panel

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


class BLENDERTORCP_PT_shader_validation(Panel):
    """RealityKit compatibility status panel."""
    bl_label = "RealityKit Compatibility"
    bl_idname = "BLENDERTORCP_PT_shader_validation"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == 'NODE_EDITOR' and space.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        material = _get_active_material(context)
        if not material:
            layout.label(text="No active material", icon='INFO')
            return

        try:
            result = rk_validate.validate_material(material, strict=True)
        except TypeError:
            result = rk_validate.validate_material(material)
            if result.get("warnings"):
                result["errors"].extend(result["warnings"])
                result["warnings"] = []
            result["ok"] = not result["errors"]
        if result["errors"]:
            layout.label(text="Incompatible material", icon='ERROR')
        elif result["warnings"]:
            layout.label(text="Compatible with warnings", icon='INFO')
        else:
            layout.label(text="Compatible", icon='CHECKMARK')

        if result["errors"]:
            layout.label(text="Errors:", icon='ERROR')
            for issue in result["errors"][:6]:
                layout.label(text=f"{issue['node_name']}: {issue['message']}")
            if len(result["errors"]) > 6:
                layout.label(text=f"{len(result['errors']) - 6} more errors")

        if result["warnings"]:
            layout.label(text="Warnings:", icon='INFO')
            for issue in result["warnings"][:6]:
                layout.label(text=f"{issue['node_name']}: {issue['message']}")
            if len(result["warnings"]) > 6:
                layout.label(text=f"{len(result['warnings']) - 6} more warnings")

        layout.separator()
        layout.operator("blendertorcp.validate_material", icon='CHECKMARK')
        layout.operator("blendertorcp.select_offending_nodes", icon='RESTRICT_SELECT_OFF')


def register():
    """Register shader editor panels."""
    bpy.utils.register_class(BLENDERTORCP_PT_shader_validation)


def unregister():
    """Unregister shader editor panels."""
    bpy.utils.unregister_class(BLENDERTORCP_PT_shader_validation)
