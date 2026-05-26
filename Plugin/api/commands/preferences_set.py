"""preferences_set command — modify addon-level preferences."""

from __future__ import annotations

_PREF_KEYS = {
    "usdzip_path",
    "materialx_library_path",
    "default_export_format",
}


def handle(args: dict) -> dict:
    import bpy
    from Plugin import prefs as addon_prefs

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

        if key == "default_export_format":
            value = str(value).upper()
            if value not in ("USDA", "USDC", "USDZ"):
                raise ValueError(f"Invalid format: '{value}'. Allowed: USDA, USDC, USDZ")

        try:
            setattr(prefs, key, value)
            updated.append(key)
        except Exception as exc:
            raise ValueError(f"Failed to set '{key}': {exc}") from exc

    return {"updated": updated}
