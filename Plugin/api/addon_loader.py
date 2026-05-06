"""Addon loading helpers shared by Blender-hosted entry points."""

from __future__ import annotations


def _candidate_module_names(addon_name: str) -> list[str]:
    """Return likely module names for a Blender addon or extension."""
    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    try:
        import addon_utils

        for module in addon_utils.modules(refresh=True):
            module_name = getattr(module, "__name__", "")
            bl_info = getattr(module, "bl_info", None) or {}
            if (
                module_name == addon_name
                or module_name.endswith(f".{addon_name}")
                or bl_info.get("name") == addon_name
            ):
                add(module_name)
    except Exception:
        pass

    add(f"bl_ext.user_default.{addon_name}")
    add(f"bl_ext.blender_local_addons.{addon_name}")
    add(addon_name)
    return names


def ensure_addon_loaded(
    addon_name: str = "BlenderToRCP",
    scene_attr: str = "blender_to_rcp_export_settings",
) -> None:
    """Enable the addon if its scene properties are not registered yet."""
    import bpy
    import sys

    if hasattr(bpy.types.Scene, scene_attr):
        return

    failures = []
    plugin_module = sys.modules.get("Plugin")
    register = getattr(plugin_module, "register", None) if plugin_module is not None else None
    if callable(register):
        try:
            register()
        except Exception as exc:
            failures.append({"module": "Plugin", "error": str(exc)})
        else:
            if hasattr(bpy.types.Scene, scene_attr):
                return
            failures.append({"module": "Plugin", "error": f"'{scene_attr}' was not registered"})

    for module_name in _candidate_module_names(addon_name):
        try:
            bpy.ops.preferences.addon_enable(module=module_name)
        except Exception as exc:
            failures.append({"module": module_name, "error": str(exc)})
            continue
        if hasattr(bpy.types.Scene, scene_attr):
            return
        failures.append({"module": module_name, "error": f"'{scene_attr}' was not registered"})

    attempted = ", ".join(item["module"] for item in failures) or addon_name
    raise RuntimeError(
        f"BlenderToRCP addon could not be loaded. Attempted: {attempted}. "
        f"Failures: {failures}"
    )
