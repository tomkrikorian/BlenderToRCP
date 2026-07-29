"""
UI modules for BlenderToRCP.
"""

_needs_reload = "bpy" in locals()

import bpy

from . import panel as _panel
from . import shader_panel as _shader_panel
from . import shader_authoring_panel as _shader_authoring_panel
from . import shader_menu as _shader_menu

if _needs_reload:
    import importlib
    _panel = importlib.reload(_panel)
    _shader_panel = importlib.reload(_shader_panel)
    _shader_authoring_panel = importlib.reload(_shader_authoring_panel)
    _shader_menu = importlib.reload(_shader_menu)


def register():
    """Register UI classes."""
    _panel.register()
    if not bpy.app.background:
        _shader_panel.register()
        _shader_authoring_panel.register()
        _shader_menu.register()


def unregister():
    """Unregister UI classes."""
    if not bpy.app.background:
        _shader_menu.unregister()
        _shader_authoring_panel.unregister()
        _shader_panel.unregister()
    _panel.unregister()
