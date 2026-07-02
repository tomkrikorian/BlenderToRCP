"""
Shader Editor panel for RealityKit compatibility status.
"""

import bpy
from bpy.types import Panel

from ..nodes import validate as rk_validate
from .draw_utils import draw_issue_list


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
            status = layout.row()
            status.alert = True
            status.label(text="Incompatible material", icon='ERROR')
        elif result["warnings"]:
            layout.label(text="Compatible with warnings", icon='INFO')
        else:
            layout.label(text="Compatible", icon='CHECKMARK')

        def _issue_text(issue):
            return f"{issue['node_name']}: {issue['message']}"

        draw_issue_list(
            layout, result["errors"],
            title="Errors", icon='ERROR', alert=True, max_items=6,
            format_item=_issue_text,
        )
        draw_issue_list(
            layout, result["warnings"],
            title="Warnings", icon='INFO', max_items=6,
            format_item=_issue_text,
        )

        layout.separator()
        layout.operator("blendertorcp.validate_material", icon='CHECKMARK')
        layout.operator("blendertorcp.select_offending_nodes", icon='RESTRICT_SELECT_OFF')


def register():
    """Register shader editor panels."""
    bpy.utils.register_class(BLENDERTORCP_PT_shader_validation)


def unregister():
    """Unregister shader editor panels."""
    bpy.utils.unregister_class(BLENDERTORCP_PT_shader_validation)
