"""
Blender USD export wrapper

Uses Blender's native USD exporter to create initial USD file,
which will then be post-processed for RealityKit compatibility.
"""

import os
import bpy
from pathlib import Path
from typing import Optional

from . import animation_export


_AXIS_TO_USD_EXPORT_ENUM = {
    "-X": "NEGATIVE_X",
    "-Y": "NEGATIVE_Y",
    "-Z": "NEGATIVE_Z",
}

_VALID_USD_EXPORT_AXES = {
    "X",
    "Y",
    "Z",
    "NEGATIVE_X",
    "NEGATIVE_Y",
    "NEGATIVE_Z",
}

_VALID_USD_EXPORT_NGON_METHODS = {"BEAUTY", "CLIP"}


def _axis_for_usd_export(value: str) -> str:
    """Map UI axis values (e.g. '-Z') to Blender USD exporter enum values."""
    if value is None:
        return value
    value = str(value).strip()
    if not value:
        return value
    if value in _VALID_USD_EXPORT_AXES:
        return value
    mapped = _AXIS_TO_USD_EXPORT_ENUM.get(value)
    if mapped:
        return mapped
    # Best-effort normalization for legacy/lowercase values.
    upper = value.upper()
    if upper in _VALID_USD_EXPORT_AXES:
        return upper
    mapped = _AXIS_TO_USD_EXPORT_ENUM.get(upper)
    if mapped:
        return mapped
    return value


def _ngon_method_for_usd_export(value: str) -> str:
    """Map UI n-gon method to Blender USD exporter enum values."""
    if value is None:
        return value
    value = str(value).strip()
    if not value:
        return value
    if value in _VALID_USD_EXPORT_NGON_METHODS:
        return value
    if value == "EAR_CLIP":
        return "CLIP"
    upper = value.upper()
    if upper in _VALID_USD_EXPORT_NGON_METHODS:
        return upper
    if upper == "EAR_CLIP":
        return "CLIP"
    return value


def export_blender_scene(context, settings, final_path: str, diagnostics=None) -> Optional[str]:
    """Export Blender scene to USD using Blender's native exporter
    
    Args:
        context: Blender context
        settings: Export settings
        final_path: Final output path
        
    Returns:
        Path to exported USD file (temporary if USDZ is requested)
    """
    export_format = getattr(settings, "export_format", "USDA")
    if export_format == 'USD':
        export_format = 'USDC'

    # Determine output path
    if export_format == 'USDZ':
        # Create temporary USD file
        temp_dir = Path(final_path).parent / ".blendertorcp_temp"
        temp_dir.mkdir(exist_ok=True)
        temp_usd = temp_dir / f"{Path(final_path).stem}.usdc"
        output_path = str(temp_usd)
    else:
        output_path = final_path
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Get export settings
    root_prim_name = settings.root_prim_name or "Scene"
    root_prim_path = root_prim_name if root_prim_name.startswith("/") else f"/{root_prim_name}"
    
    # Configure Blender USD export
    # Note: This uses Blender's built-in USD exporter
    # We'll use the operator directly
    
    # Save current selection
    original_selection = [obj for obj in context.selected_objects]
    original_active = context.active_object
    animation_state = None
    
    try:
        usd_format = _usd_format_for_path(output_path)
        
        # Set up export parameters
        export_custom_properties = bool(getattr(settings, "export_custom_properties", True))
        author_blender_name = bool(getattr(settings, "author_blender_name", True)) if export_custom_properties else False
        custom_properties_namespace = getattr(settings, "custom_properties_namespace", "userProperties") if export_custom_properties else ""

        export_kwargs = {
            'filepath': output_path,
            'check_existing': False,
            'filter_glob': '*.usd;*.usda;*.usdc',
            'selected_objects_only': bool(getattr(settings, "selected_objects_only", False)),
            'export_animation': bool(getattr(settings, "export_animation", False)),
            'export_hair': bool(getattr(settings, "export_hair", False)),
            'export_uvmaps': bool(getattr(settings, "export_uvmaps", True)),
            'rename_uvmaps': bool(getattr(settings, "rename_uvmaps", True)),
            'export_normals': bool(getattr(settings, "export_normals", True)),
            'export_materials': True,  # We'll rewrite these, but need initial export
            'export_textures': False,  # We'll handle textures separately
            'use_instancing': bool(getattr(settings, "use_instancing", True)),
            'evaluation_mode': getattr(settings, "evaluation_mode", 'RENDER'),
            'default_prim_path': root_prim_path,
            'root_prim_path': root_prim_path,
            'default_usd_format': usd_format,
            'export_texture_dir': '',
            'export_custom_properties': export_custom_properties,
            'custom_properties_namespace': custom_properties_namespace,
            'author_blender_name': author_blender_name,
            'allow_unicode': bool(getattr(settings, "allow_unicode", True)),
            'relative_paths': bool(getattr(settings, "relative_paths", True)),
            'convert_orientation': bool(getattr(settings, "convert_orientation", False)),
            'export_global_forward_selection': _axis_for_usd_export(
                getattr(settings, "forward_axis", "-Z")
            ),
            'export_global_up_selection': _axis_for_usd_export(
                getattr(settings, "up_axis", "Y")
            ),
            'convert_scene_units': getattr(settings, "convert_scene_units", 'METERS'),
            'meters_per_unit': float(getattr(settings, "meters_per_unit", 1.0)),
            'xform_op_mode': getattr(settings, "xform_op_mode", 'TRS'),
            'export_meshes': bool(getattr(settings, "export_meshes", True)),
            'export_lights': bool(getattr(settings, "export_lights", True)),
            'convert_world_material': bool(getattr(settings, "convert_world_material", True)),
            'export_cameras': bool(getattr(settings, "export_cameras", True)),
            'export_curves': bool(getattr(settings, "export_curves", True)),
            'export_points': bool(getattr(settings, "export_points", True)),
            'export_volumes': bool(getattr(settings, "export_volumes", True)),
            'export_armatures': bool(getattr(settings, "export_armatures", True)),
            'only_deform_bones': bool(getattr(settings, "only_deform_bones", False)),
            'export_shapekeys': bool(getattr(settings, "export_shapekeys", True)),
            'merge_parent_xform': bool(getattr(settings, "merge_parent_xform", False)),
            'triangulate_meshes': bool(getattr(settings, "triangulate_meshes", False)),
            'quad_method': getattr(settings, "quad_method", 'SHORTEST_DIAGONAL'),
            'ngon_method': _ngon_method_for_usd_export(
                getattr(settings, "ngon_method", "BEAUTY")
            ),
            'export_subdivision': getattr(settings, "export_subdivision", 'BEST_MATCH'),
        }
        
        # Orientation handled via convert_orientation/forward_axis/up_axis settings.
        
        # If exporting animations, ensure all actions are serialized into a single NLA
        # track so downstream tools (Reality Composer Pro) can clip the timeline.
        animation_state = animation_export.prepare_animation_export(context, settings, diagnostics)

        # Call Blender's USD exporter
        # Note: In Blender 5.0+, this is available as an operator
        export_kwargs = _filter_export_kwargs(bpy.ops.wm.usd_export, export_kwargs)
        bpy.ops.wm.usd_export(**export_kwargs)
        
        if not os.path.exists(output_path):
            raise RuntimeError(f"USD export failed: {output_path} not created")
        
        return output_path
        
    except Exception as e:
        # Check if USD exporter is available
        if not hasattr(bpy.ops.wm, 'usd_export'):
            raise RuntimeError(
                "Blender USD exporter not available. "
                "Please ensure you're using Blender 3.0+ with USD support enabled."
            ) from e
        raise
    
    finally:
        if animation_state is not None:
            animation_export.restore_animation_export(animation_state)

        # Restore selection
        try:
            for obj in context.view_layer.objects:
                obj.select_set(False)
        except Exception:
            pass
        for obj in original_selection:
            try:
                obj.select_set(True)
            except Exception:
                pass
        if original_active:
            try:
                context.view_layer.objects.active = original_active
            except Exception:
                pass


def get_export_settings(context, settings) -> dict:
    """Get export settings dictionary for Blender USD exporter"""
    return {
        'filepath': settings.filepath,
        'check_existing': False,
        'selected_objects_only': bool(getattr(settings, "selected_objects_only", False)),
        'export_animation': bool(getattr(settings, "export_animation", False)),
        'export_hair': bool(getattr(settings, "export_hair", False)),
        'export_uvmaps': bool(getattr(settings, "export_uvmaps", True)),
        'rename_uvmaps': bool(getattr(settings, "rename_uvmaps", True)),
        'export_normals': bool(getattr(settings, "export_normals", True)),
        'export_materials': True,
        'export_textures': False,
        'use_instancing': bool(getattr(settings, "use_instancing", True)),
        'evaluation_mode': getattr(settings, "evaluation_mode", 'RENDER'),
        'export_custom_properties': bool(getattr(settings, "export_custom_properties", True)),
        'custom_properties_namespace': getattr(settings, "custom_properties_namespace", "userProperties")
        if getattr(settings, "export_custom_properties", True)
        else "",
        'author_blender_name': bool(getattr(settings, "author_blender_name", True))
        if getattr(settings, "export_custom_properties", True)
        else False,
        'allow_unicode': bool(getattr(settings, "allow_unicode", True)),
        'relative_paths': bool(getattr(settings, "relative_paths", True)),
        'convert_orientation': bool(getattr(settings, "convert_orientation", False)),
        'export_global_forward_selection': _axis_for_usd_export(
            getattr(settings, "forward_axis", "-Z")
        ),
        'export_global_up_selection': _axis_for_usd_export(
            getattr(settings, "up_axis", "Y")
        ),
        'convert_scene_units': getattr(settings, "convert_scene_units", 'METERS'),
        'meters_per_unit': float(getattr(settings, "meters_per_unit", 1.0)),
        'xform_op_mode': getattr(settings, "xform_op_mode", 'TRS'),
        'export_meshes': bool(getattr(settings, "export_meshes", True)),
        'export_lights': bool(getattr(settings, "export_lights", True)),
        'convert_world_material': bool(getattr(settings, "convert_world_material", True)),
        'export_cameras': bool(getattr(settings, "export_cameras", True)),
        'export_curves': bool(getattr(settings, "export_curves", True)),
        'export_points': bool(getattr(settings, "export_points", True)),
        'export_volumes': bool(getattr(settings, "export_volumes", True)),
        'export_armatures': bool(getattr(settings, "export_armatures", True)),
        'only_deform_bones': bool(getattr(settings, "only_deform_bones", False)),
        'export_shapekeys': bool(getattr(settings, "export_shapekeys", True)),
        'merge_parent_xform': bool(getattr(settings, "merge_parent_xform", False)),
        'triangulate_meshes': bool(getattr(settings, "triangulate_meshes", False)),
        'quad_method': getattr(settings, "quad_method", 'SHORTEST_DIAGONAL'),
        'ngon_method': _ngon_method_for_usd_export(getattr(settings, "ngon_method", "BEAUTY")),
        'export_subdivision': getattr(settings, "export_subdivision", 'BEST_MATCH'),
    }


def _filter_export_kwargs(operator, kwargs: dict) -> dict:
    """Filter kwargs to only those supported by the USD export operator."""
    try:
        valid_props = {prop.identifier for prop in operator.get_rna_type().properties}
    except Exception:
        return kwargs
    return {key: value for key, value in kwargs.items() if key in valid_props}


def _usd_format_for_path(output_path: str) -> str:
    """Choose USD format based on file extension."""
    suffix = Path(output_path).suffix.lower()
    if suffix == ".usda":
        return "usda"
    if suffix in {".usdc", ".usd"}:
        return "usdc"
    return "usdc"
