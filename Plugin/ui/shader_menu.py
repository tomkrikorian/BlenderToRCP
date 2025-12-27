"""
Shader Editor add-menu integration for RealityKit nodes.
"""

import bpy

from ..nodes import metadata as rk_metadata

MENU_IDNAME = "BLENDERTORCP_MT_shader_nodes"


def _draw_node_items(layout):
    entries = rk_metadata.get_node_catalog()
    if not entries:
        layout.label(text="No RealityKit nodes found")
        return
    for entry in entries:
        props = layout.operator("blendertorcp.add_rk_node", text=entry["label"])
        props.rk_node_id = entry["id"]
        if entry["id"] in {"rk_pbr", "rk_unlit"}:
            props.auto_connect = True


class BLENDERTORCP_MT_shader_nodes(bpy.types.Menu):
    """RealityKit node menu for the Shader Editor."""

    bl_label = "RealityKit Nodes"
    bl_idname = MENU_IDNAME

    def draw(self, _context):
        layout = self.layout
        _draw_node_items(layout)


def _draw_add_menu(self, context):
    layout = self.layout
    layout.separator()
    if getattr(context, "is_menu_search", False):
        _draw_node_items(layout)
    else:
        layout.menu(MENU_IDNAME)


def register():
    """Register the RealityKit Nodes menu in the Shader Editor."""
    if bpy.app.background:
        return
    bpy.utils.register_class(BLENDERTORCP_MT_shader_nodes)
    bpy.types.NODE_MT_shader_node_add_all.append(_draw_add_menu)


def unregister():
    """Unregister the RealityKit Nodes menu."""
    if bpy.app.background:
        return
    try:
        bpy.types.NODE_MT_shader_node_add_all.remove(_draw_add_menu)
    except Exception:
        pass
    try:
        bpy.utils.unregister_class(BLENDERTORCP_MT_shader_nodes)
    except Exception:
        pass
