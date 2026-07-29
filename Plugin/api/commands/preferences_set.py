"""preferences_set command — modify addon-level preferences."""

from __future__ import annotations

_PREF_KEYS = {
    "usdzip_path",
}


def handle(args: dict) -> dict:
    import bpy
    from ... import prefs as addon_prefs

    settings_dict = args.get("settings", {})
    if not settings_dict:
        raise ValueError("No settings provided. Pass 'settings': {'key': value, ...}")

    prefs = addon_prefs.get_preferences(bpy.context)
    if prefs is None:
        raise RuntimeError("BlenderToRCP addon preferences not available.")

    updated = []
    for key, value in settings_dict.items():
        if key not in _PREF_KEYS:
            raise ValueError(f"Unknown preference key: '{key}'. Available: {sorted(_PREF_KEYS)}")

        try:
            setattr(prefs, key, value)
            updated.append(key)
        except Exception as exc:
            raise ValueError(f"Failed to set '{key}': {exc}") from exc

    # Each CLI call is a fresh Blender process; without an explicit userpref
    # save the change would die with this process.
    bpy.ops.wm.save_userpref()

    return {"updated": updated}
