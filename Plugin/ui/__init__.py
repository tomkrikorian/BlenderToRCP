"""
UI modules for BlenderToRCP.
"""

_needs_reload = "bpy" in locals()

import bpy

from . import panel as _panel
from . import shader_panel as _shader_panel

if _needs_reload:
    import importlib
    _panel = importlib.reload(_panel)
    _shader_panel = importlib.reload(_shader_panel)


def register():
    """Register UI classes."""
    _panel.register()
    if not bpy.app.background:
        _shader_panel.register()


def unregister():
    """Unregister UI classes."""
    if not bpy.app.background:
        _shader_panel.unregister()
    _panel.unregister()
