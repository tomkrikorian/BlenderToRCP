"""validate command — check materials for RealityKit compatibility."""

from __future__ import annotations

from ._settings_common import (
    MATERIALX_SURFACE_PROFILE_DEFAULT,
    MATERIALX_SURFACE_PROFILES,
    get_settings,
)


def _resolve_surface_profile(args: dict, settings) -> str:
    """Resolve and validate the MaterialX profile used by this validation run."""
    requested = args.get("materialx_surface_profile")
    if requested is None:
        requested = getattr(
            settings,
            "materialx_surface_profile",
            MATERIALX_SURFACE_PROFILE_DEFAULT,
        )

    canonical = {
        profile.casefold(): profile for profile in MATERIALX_SURFACE_PROFILES
    }.get(str(requested).strip().casefold())
    if canonical is None:
        raise ValueError(
            f"Invalid materialx_surface_profile '{requested}'. "
            f"Allowed: {list(MATERIALX_SURFACE_PROFILES)}"
        )
    return canonical


def handle(args: dict) -> dict:
    import bpy
    from ...nodes import validate as rk_validate

    material_name = args.get("material")
    strict = args.get("strict", False)
    only_errors = args.get("only_errors", False)
    surface_profile = _resolve_surface_profile(args, get_settings())

    if material_name:
        mat = bpy.data.materials.get(material_name)
        if mat is None:
            raise ValueError(f"Material not found: '{material_name}'")
        materials = [mat]
    else:
        materials = rk_validate.collect_scene_materials(bpy.context)

    results = []
    total_errors = 0
    total_warnings = 0

    for mat in materials:
        result = rk_validate.validate_material(
            mat,
            strict=strict,
            surface_profile=surface_profile,
        )
        entry = {
            "name": result["material"],
            "ok": result["ok"],
            "errors": [
                {
                    "node_name": e.get("node_name", ""),
                    "node_type": e.get("node_type", ""),
                    "message": e.get("message", ""),
                }
                for e in result["errors"]
            ],
        }
        if not only_errors:
            entry["warnings"] = [
                {
                    "node_name": w.get("node_name", ""),
                    "node_type": w.get("node_type", ""),
                    "message": w.get("message", ""),
                }
                for w in result["warnings"]
            ]
            total_warnings += len(result["warnings"])
        total_errors += len(result["errors"])
        results.append(entry)

    all_ok = total_errors == 0
    summary = {
        "ok": all_ok,
        "error_count": total_errors,
        "materialx_surface_profile": surface_profile,
        "materials": results,
    }
    if not only_errors:
        summary["warning_count"] = total_warnings
    return summary
