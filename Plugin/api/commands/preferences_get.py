"""preferences_get command — read addon-level preferences."""

from __future__ import annotations

_PREF_KEYS = (
    "usdzip_path",
    "materialx_library_path",
    "default_export_format",
)


def handle(args: dict) -> dict:
    import bpy
    from Plugin import prefs as addon_prefs

    prefs = addon_prefs.get_preferences(bpy.context)
    if prefs is None:
        raise RuntimeError("BlenderToRCP addon preferences not available.")

    return {key: getattr(prefs, key, None) for key in _PREF_KEYS}
