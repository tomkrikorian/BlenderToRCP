"""
Add-on preferences for BlenderToRCP
"""

from __future__ import annotations

import bpy
import json
from pathlib import Path
from bpy.props import StringProperty, EnumProperty
from bpy.types import AddonPreferences

from .api.addon_loader import _candidate_module_names
from .api.commands._settings_common import (
    INTERNAL_KEYS,
    REALITYKIT_OS27_PROFILE_NAME,
)


EXPORT_SETTINGS_PAYLOAD_SCHEMA = "blendertorcp.export-settings"
EXPORT_SETTINGS_PAYLOAD_VERSION = 3
EXPORT_SETTINGS_PROFILE = REALITYKIT_OS27_PROFILE_NAME
EXPORT_SETTINGS_SCENE_SCHEMA_KEY = "_blendertorcp_export_settings_schema_version"
EXPORT_SETTINGS_SKIP_KEYS = frozenset({*INTERNAL_KEYS, "filepath"})


def get_addon_module_name(context=None) -> str:
    """Get the add-on module name for preferences lookup."""
    if context is None:
        context = bpy.context

    addons = getattr(getattr(context, "preferences", None), "addons", None)
    if addons is not None:
        for addon_name in _candidate_module_names("BlenderToRCP"):
            if addons.get(addon_name) is not None:
                return addon_name

    if __package__ and __package__ != "Plugin":
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


def get_preferences(context=None):
    """Get add-on preferences"""
    if context is None:
        context = bpy.context
    addon_name = get_addon_module_name(context)
    addon = context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None


def _settings_property_defs(settings) -> dict[str, object]:
    properties = getattr(getattr(settings, "bl_rna", None), "properties", [])
    return {
        prop.identifier: prop
        for prop in properties
        if getattr(prop, "identifier", None)
    }


def _raw_settings_keys(settings) -> set[str]:
    try:
        return {str(key) for key in settings.keys()}
    except Exception:
        return set()


def _raw_settings_value(settings, key: str, default=None):
    try:
        return settings.get(key, default)
    except Exception:
        try:
            return settings[key]
        except Exception:
            return default


def _write_raw_settings_value(settings, key: str, value) -> None:
    settings[key] = value


def export_settings_scene_is_current(settings) -> bool:
    """Return whether saved scene ID-properties use the current settings schema."""
    return (
        _raw_settings_value(settings, EXPORT_SETTINGS_SCENE_SCHEMA_KEY)
        == EXPORT_SETTINGS_PAYLOAD_VERSION
    )


def _reset_scene_export_settings(settings) -> None:
    """Remove all saved PropertyGroup values so Blender RNA defaults win."""
    prop_defs = _settings_property_defs(settings)
    try:
        settings.persist_suspended = True
    except Exception:
        pass

    for key in prop_defs:
        if key in {"rna_type", "persist_suspended"}:
            continue
        try:
            settings.property_unset(key)
            continue
        except Exception:
            pass
        try:
            del settings[key]
        except Exception:
            pass

    # A dedicated PropertyGroup should not retain unknown pre-release keys.
    for key in _raw_settings_keys(settings):
        if key == "persist_suspended":
            continue
        try:
            del settings[key]
        except Exception:
            pass

    _write_raw_settings_value(
        settings,
        EXPORT_SETTINGS_SCENE_SCHEMA_KEY,
        EXPORT_SETTINGS_PAYLOAD_VERSION,
    )
    try:
        settings.persist_suspended = False
    except Exception:
        pass
    try:
        settings.history_applied = False
    except Exception:
        pass


def ensure_current_export_settings_scene_profile(settings) -> bool:
    """Stamp a new scene or reset saved settings from an older add-on build.

    Returns True when legacy scene ID-properties were discarded. A pristine
    PropertyGroup has no saved keys, so it is stamped without needlessly
    touching its current RNA defaults.
    """
    if export_settings_scene_is_current(settings):
        return False

    raw_keys = _raw_settings_keys(settings)
    legacy_keys = raw_keys - {EXPORT_SETTINGS_SCENE_SCHEMA_KEY}
    if legacy_keys:
        _reset_scene_export_settings(settings)
        return True

    _write_raw_settings_value(
        settings,
        EXPORT_SETTINGS_SCENE_SCHEMA_KEY,
        EXPORT_SETTINGS_PAYLOAD_VERSION,
    )
    return False


def build_export_settings_payload(settings) -> dict:
    """Build the only persisted export-settings payload accepted by 2.0."""
    values = {}
    for key in _settings_property_defs(settings):
        if key in EXPORT_SETTINGS_SKIP_KEYS:
            continue
        try:
            values[key] = getattr(settings, key)
        except Exception:
            continue
    return {
        "schema": EXPORT_SETTINGS_PAYLOAD_SCHEMA,
        "version": EXPORT_SETTINGS_PAYLOAD_VERSION,
        "profile": EXPORT_SETTINGS_PROFILE,
        "values": values,
    }


def serialize_export_settings_payload(settings) -> str:
    return json.dumps(
        build_export_settings_payload(settings),
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_export_settings_payload(serialized: str) -> tuple[str, dict | None]:
    if not serialized:
        return "missing", None
    try:
        payload = json.loads(serialized)
    except Exception:
        return "invalid", None
    if not isinstance(payload, dict):
        return "invalid", None

    versioned_keys = {"schema", "version", "profile", "values"}
    if not versioned_keys.issubset(payload):
        return "unversioned", None
    if payload.get("schema") != EXPORT_SETTINGS_PAYLOAD_SCHEMA:
        return "invalid", None
    if payload.get("version") != EXPORT_SETTINGS_PAYLOAD_VERSION:
        return "old_version", None
    if payload.get("profile") != EXPORT_SETTINGS_PROFILE:
        return "wrong_profile", None
    values = payload.get("values")
    if not isinstance(values, dict):
        return "invalid", None
    return "current", values


def _persisted_value_is_valid(prop, value) -> bool:
    prop_type = getattr(prop, "type", None)
    if prop_type == "BOOLEAN":
        return type(value) is bool
    if prop_type == "INT":
        return type(value) is int
    if prop_type == "FLOAT":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if prop_type == "STRING":
        return isinstance(value, str)
    if prop_type == "ENUM":
        if not isinstance(value, str):
            return False
        try:
            valid = {item.identifier for item in prop.enum_items}
        except Exception:
            return True
        return value in valid
    return True


def _apply_export_settings_values(settings, values: dict) -> bool:
    prop_defs = _settings_property_defs(settings)
    expected_keys = {
        key for key in prop_defs if key not in EXPORT_SETTINGS_SKIP_KEYS
    }
    if set(values) != expected_keys:
        return False
    if any(
        not _persisted_value_is_valid(prop_defs[key], value)
        for key, value in values.items()
    ):
        return False

    previous = {}
    for key in values:
        try:
            previous[key] = getattr(settings, key)
        except Exception:
            return False

    try:
        settings.persist_suspended = True
    except Exception:
        pass
    try:
        for key, value in values.items():
            setattr(settings, key, value)
    except Exception:
        for key, value in previous.items():
            try:
                setattr(settings, key, value)
            except Exception:
                pass
        return False
    finally:
        try:
            settings.persist_suspended = False
        except Exception:
            pass
    return True


def persist_export_settings(context, settings, *, remember_path: bool = True) -> bool:
    """Persist current settings under the strict versioned profile."""
    prefs = get_preferences(context) if context is not None else None
    if not prefs:
        return False
    ensure_current_export_settings_scene_profile(settings)
    try:
        prefs.last_export_settings_json = serialize_export_settings_payload(settings)
    except Exception:
        return False
    if remember_path and context is not None:
        set_last_export_path(
            context,
            getattr(settings, "filepath", ""),
            getattr(getattr(context, "blend_data", None), "filepath", None),
        )
    return True


def apply_persisted_export_settings(context, settings) -> dict:
    """Apply only the current version/profile, resetting every older format."""
    scene_reset = ensure_current_export_settings_scene_profile(settings)
    if (
        getattr(settings, "history_applied", False)
        and export_settings_scene_is_current(settings)
        and not scene_reset
    ):
        return {"status": "already_applied", "scene_reset": False}

    prefs = get_preferences(context)
    if not prefs:
        settings.history_applied = True
        return {"status": "no_preferences", "scene_reset": scene_reset}

    status, values = _decode_export_settings_payload(
        getattr(prefs, "last_export_settings_json", "")
    )
    if status == "current":
        if not _apply_export_settings_values(settings, values or {}):
            status = "invalid_values"

    if status not in {"current", "missing"}:
        _reset_scene_export_settings(settings)
        scene_reset = True

    if not getattr(settings, "filepath", ""):
        apply_last_export_path(context, settings)

    settings.history_applied = True

    # Empty and rejected payloads are rewritten immediately so a legacy value
    # cannot be retried on the next scene or Blender launch.
    if status != "current":
        try:
            prefs.last_export_settings_json = serialize_export_settings_payload(settings)
        except Exception:
            pass

    return {"status": status, "scene_reset": scene_reset}


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


def apply_last_export_path(
    context=None,
    settings=None,
    blend_path: str | Path | None = None,
) -> bool:
    """Apply the last remembered output path for a .blend to export settings."""
    if settings is None:
        return False

    key_path = blend_path
    if key_path is None and context is not None:
        key_path = getattr(getattr(context, "blend_data", None), "filepath", None)

    if not key_path:
        try:
            settings.filepath = ""
        except Exception:
            pass
        return False

    last_path = get_last_export_path(context, key_path)
    if not last_path:
        return False

    try:
        settings.filepath = last_path
    except Exception:
        return False
    return True


def register():
    """Register add-on preferences."""
    bpy.utils.register_class(BlenderToRCPPreferences)


def unregister():
    """Unregister add-on preferences."""
    bpy.utils.unregister_class(BlenderToRCPPreferences)
