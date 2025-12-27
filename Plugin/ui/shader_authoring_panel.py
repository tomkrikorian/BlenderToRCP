"""
Shader Editor panel for RealityKit authoring tools.
"""

import bpy
from bpy.types import Panel


class BLENDERTORCP_PT_shader_authoring(Panel):
    """RealityKit authoring tools (material editor only)."""

    bl_label = "RealityKit Authoring"
    bl_idname = "BLENDERTORCP_PT_shader_authoring"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "RCP Exporter"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if not space or space.type != 'NODE_EDITOR':
            return False
        if getattr(space, "tree_type", None) != 'ShaderNodeTree':
            return False
        if getattr(space, "shader_type", None) != 'OBJECT':
            return False

        material = context.material
        if material is None and context.object:
            material = context.object.active_material
        return bool(material and material.use_nodes)

    def draw(self, context):
        layout = self.layout
        layout.operator("blendertorcp.insert_pbr_group", icon='NODE_MATERIAL', text="Insert RK PBR Group")
        layout.operator("blendertorcp.insert_unlit_group", icon='NODE_MATERIAL', text="Insert RK Unlit Group")


def register():
    bpy.utils.register_class(BLENDERTORCP_PT_shader_authoring)


def unregister():
    bpy.utils.unregister_class(BLENDERTORCP_PT_shader_authoring)
