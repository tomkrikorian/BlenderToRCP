"""Shared helpers for settings commands."""

from __future__ import annotations

# Keys that are internal bookkeeping and should not be exposed via the CLI
INTERNAL_KEYS = frozenset({
    "rna_type",
    "name",
    "history_applied",
    "last_diagnostics_path",
    "persist_suspended",
    "background_job_dir",
    "background_job_pid",
    "force_unlit_materials",
})

SETTING_GROUPS: dict[str, set[str]] = {
    "general": {
        "filepath",
        "export_format",
        "root_prim_name",
        "export_animation",
        "author_animation_library",
        "selected_objects_only",
        "export_custom_properties",
        "custom_properties_namespace",
        "author_blender_name",
        "allow_unicode",
        "relative_paths",
        "convert_orientation",
        "forward_axis",
        "up_axis",
        "convert_scene_units",
        "meters_per_unit",
        "xform_op_mode",
        "evaluation_mode",
        "use_instancing",
    },
    "objects": {
        "export_meshes",
        "export_lights",
        "convert_world_material",
        "export_cameras",
        "export_curves",
        "export_points",
        "export_volumes",
        "export_hair",
    },
    "geometry": {
        "export_uvmaps",
        "rename_uvmaps",
        "export_normals",
        "merge_parent_xform",
        "triangulate_meshes",
        "quad_method",
        "ngon_method",
        "export_subdivision",
    },
    "rigging": {
        "export_armatures",
        "only_deform_bones",
        "export_shapekeys",
    },
    "texture": {
        "export_texture_settings_enabled",
        "bake_resolution",
        "bake_resolution_custom",
        "bake_image_format",
        "bake_margin",
    },
    "bake": {
        "bake_mode",
        "bake_ibl_source",
        "bake_ibl_filepath",
        "bake_ibl_strength",
        "bake_ibl_rotation",
        "bake_isolate_meshes_lit",
        "bake_base_color",
        "bake_opacity",
        "bake_keep_materials",
        "bake_step_timeout_seconds",
        "bake_roughness_mode",
        "apply_yup_geometry",
    },
    "diagnostics": {
        "diagnostics_enabled",
    },
}


def get_settings():
    """Return the scene export settings PropertyGroup instance."""
    import bpy

    settings = getattr(bpy.context.scene, "blender_to_rcp_export_settings", None)
    if settings is None:
        raise RuntimeError("BlenderToRCP addon not loaded — export settings unavailable.")
    return settings


def coerce_value(prop, value):
    """Coerce a CLI string/JSON value to the correct Python type for a Blender property."""
    if prop.type == "BOOLEAN":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    if prop.type == "INT":
        return int(value)

    if prop.type == "FLOAT":
        return float(value)

    if prop.type == "ENUM":
        s = str(value).upper()
        valid = {item.identifier for item in prop.enum_items}
        if s not in valid:
            raise ValueError(
                f"Invalid value '{value}' for '{prop.identifier}'. "
                f"Allowed: {sorted(valid)}"
            )
        return s

    if prop.type == "STRING":
        return str(value)

    return value
