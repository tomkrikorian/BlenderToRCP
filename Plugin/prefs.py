"""
Add-on preferences for BlenderToRCP
"""

import bpy
import json
from pathlib import Path
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import AddonPreferences


def get_addon_module_name() -> str:
    """Get the add-on module name for preferences lookup."""
    if __package__:
        return __package__
    return __name__.rpartition('.')[0] or __name__


class BlenderToRCPPreferences(AddonPreferences):
    """Add-on preferences stored in Blender preferences"""
    bl_idname = get_addon_module_name()
    
    # USD tool paths
    usdzip_path: StringProperty(
        name="USDZ Packager Path",
        description="Path to usdzip tool (optional, will use Python fallback if empty)",
        default="",
        subtype='FILE_PATH',
        maxlen=1024
    )
    
    # MaterialX library path
    materialx_library_path: StringProperty(
        name="MaterialX Library Path",
        description="Path to MaterialX library directory (optional, uses bundled if empty)",
        default="",
        subtype='DIR_PATH',
        maxlen=1024
    )
    
    # Default export settings
    default_export_format: EnumProperty(
        name="Default Export Format",
        description="Default format for exports",
        items=[
            ('USDA', "USD ASCII (.usda)", "Export as USD ASCII (.usda)"),
            ('USDC', "USD Binary (.usdc)", "Export as USD binary (.usdc)"),
            ('USDZ', "USDZ Package (.usdz)", "Export as USDZ package (.usdz)"),
        ],
        default='USDA'
    )
    
    # Diagnostics
    enable_diagnostics: BoolProperty(
        name="Enable Diagnostics",
        description="Generate detailed export diagnostics JSON",
        default=True
    )

    enforcement_mode: EnumProperty(
        name="RealityKit Enforcement",
        description="Strict export mode (always blocks on unsupported nodes)",
        items=[
            ('BLOCK_EXPORT', "Strict (Block Export)", "Prevent export when unsupported nodes are found"),
        ],
        default='BLOCK_EXPORT',
        options={'HIDDEN'},
    )

    last_export_settings_json: StringProperty(
        name="Last Export Settings",
        description="Serialized last used export settings",
        default="",
        options={'HIDDEN'}
    )

    last_export_paths_json: StringProperty(
        name="Last Export Paths",
        description="Per-.blend export path mapping",
        default="",
        options={'HIDDEN'}
    )
    
    def draw(self, context):
        """Draw preferences UI"""
        layout = self.layout
        
        # USD tooling
        box = layout.box()
        box.label(text="USD Tooling", icon='SETTINGS')
        box.prop(self, "usdzip_path")
        box.label(text="Leave empty to use built-in Python packager", icon='INFO')
        
        # MaterialX
        box = layout.box()
        box.label(text="MaterialX Library", icon='MATERIAL')
        box.prop(self, "materialx_library_path")
        box.label(text="Leave empty to use bundled MaterialX definitions", icon='INFO')
        
        # Defaults
        box = layout.box()
        box.label(text="Default Settings", icon='PREFERENCES')
        box.prop(self, "default_export_format")
        box.prop(self, "enable_diagnostics")
        # Strict mode only; no UI toggle.


def get_preferences(context=None):
    """Get add-on preferences"""
    if context is None:
        context = bpy.context
    addon_name = get_addon_module_name()
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None


def _blend_key(path: str | Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve())
    except Exception:
        return str(path)


def get_last_export_path(context=None, blend_path: str | Path | None = None) -> str | None:
    prefs = get_preferences(context)
    if not prefs:
        return None
    key = _blend_key(blend_path)
    if key is None:
        if context is None:
            return None
        key = _blend_key(getattr(context.blend_data, "filepath", None))
    if key is None:
        return None
    try:
        data = json.loads(prefs.last_export_paths_json or "{}")
    except Exception:
        data = {}
    return data.get(key)


def set_last_export_path(
    context=None,
    export_path: str | None = None,
    blend_path: str | Path | None = None,
) -> None:
    if not export_path:
        return
    prefs = get_preferences(context)
    if not prefs:
        return
    key = _blend_key(blend_path)
    if key is None and context is not None:
        key = _blend_key(getattr(context.blend_data, "filepath", None))
    if key is None:
        return
    try:
        data = json.loads(prefs.last_export_paths_json or "{}")
    except Exception:
        data = {}
    data[key] = export_path
    try:
        prefs.last_export_paths_json = json.dumps(data)
    except Exception:
        pass


def register():
    """Register add-on preferences."""
    bpy.utils.register_class(BlenderToRCPPreferences)


def unregister():
    """Unregister add-on preferences."""
    bpy.utils.unregister_class(BlenderToRCPPreferences)
