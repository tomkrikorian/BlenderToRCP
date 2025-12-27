"""
Texture baking utilities for Bake & Export.

Bakes base color and optional opacity textures per object/material.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import re

import bpy


class BakeResult:
    """Holds bake session data for restoration/cleanup."""

    def __init__(self):
        self.original_materials: Dict[object, List[Optional[object]]] = {}
        self.baked_materials: List[object] = []
        self.baked_images: List[object] = []


def bake_materials_for_objects(
    context,
    settings,
    objects,
    output_dir: Path,
    diagnostics=None,
    progress_callback=None,
) -> BakeResult:
    """Bake textures for mesh objects and replace their materials with baked versions."""
    result = BakeResult()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resolution = _resolve_bake_resolution(settings)
    margin = int(getattr(settings, "bake_margin", 8))
    bake_base = bool(getattr(settings, "bake_base_color", True))
    bake_opacity = bool(getattr(settings, "bake_opacity", True))

    mesh_objects = [obj for obj in objects if getattr(obj, "type", None) == 'MESH']
    total_steps = 0
    if mesh_objects:
        for obj in mesh_objects:
            has_materials = any(slot.material for slot in obj.material_slots)
            if bake_base and has_materials:
                total_steps += 1
            if bake_opacity and has_materials:
                total_steps += 1
    if total_steps <= 0:
        total_steps = 1
    completed_steps = 0

    def _report_progress(message: str) -> None:
        if progress_callback:
            try:
                progress_callback(completed_steps / float(total_steps), message)
            except Exception:
                pass

    for obj in mesh_objects:
        if obj.type != 'MESH':
            continue

        uv_layer_name = _get_active_uv(obj)
        if not uv_layer_name:
            msg = f"Bake failed: '{obj.name}' has no UV map."
            if diagnostics:
                diagnostics.add_error(msg)
            raise RuntimeError(msg)

        original_mats = [slot.material for slot in obj.material_slots]
        result.original_materials[obj] = original_mats

        baked_entries = []
        for slot_index, slot in enumerate(obj.material_slots):
            source_mat = slot.material
            if not source_mat:
                baked_entries.append(None)
                continue

            baked_mat = source_mat.copy()
            baked_mat.use_nodes = True
            baked_mat.name = _unique_name(f"{source_mat.name}_Baked", bpy.data.materials)
            if not source_mat.use_nodes:
                _initialize_simple_material(baked_mat, source_mat)
            slot.material = baked_mat
            result.baked_materials.append(baked_mat)

            entry = {
                "material": baked_mat,
                "base_image": None,
                "opacity_image": None,
                "use_opacity": _material_needs_opacity(source_mat),
                "uv_layer": uv_layer_name,
                "slot_index": slot_index,
            }

            if bake_base:
                base_image_path = _make_image_path(
                    output_dir,
                    obj.name,
                    baked_mat.name,
                    "baseColor",
                    ".png",
                )
                base_image = _create_bake_image(
                    name=f"{obj.name}_{baked_mat.name}_baseColor",
                    filepath=base_image_path,
                    width=resolution,
                    height=resolution,
                    colorspace="sRGB",
                )
                entry["base_image"] = base_image
                result.baked_images.append(base_image)
                _set_active_image_node(baked_mat, base_image, uv_layer_name)

            baked_entries.append(entry)

        has_materials = any(entry for entry in baked_entries)
        has_base_targets = any(entry and entry.get("base_image") for entry in baked_entries)
        if bake_base and has_base_targets:
            _report_progress(f"Baking base color: {obj.name}")
            _select_object(context, obj)
            _bake_object_pass(
                context,
                obj,
                bake_type='DIFFUSE',
                pass_filter={'COLOR'},
                margin=margin,
            )
            completed_steps += 1
            for entry in baked_entries:
                if not entry or not entry.get("base_image"):
                    continue
                entry["base_image"].save()

        if bake_opacity and has_materials:
            _report_progress(f"Baking opacity: {obj.name}")
            for entry in baked_entries:
                if not entry:
                    continue
                baked_mat = entry["material"]
                opacity_image_path = _make_image_path(
                    output_dir,
                    obj.name,
                    baked_mat.name,
                    "opacity",
                    ".png",
                )
                opacity_image = _create_bake_image(
                    name=f"{obj.name}_{baked_mat.name}_opacity",
                    filepath=opacity_image_path,
                    width=resolution,
                    height=resolution,
                    colorspace="Non-Color",
                )
                entry["opacity_image"] = opacity_image
                result.baked_images.append(opacity_image)
                _set_active_image_node(baked_mat, opacity_image, entry["uv_layer"])
                _configure_emission_for_alpha(baked_mat)

            _select_object(context, obj)
            _bake_object_pass(
                context,
                obj,
                bake_type='EMIT',
                pass_filter=None,
                margin=margin,
            )
            completed_steps += 1
            for entry in baked_entries:
                if not entry or not entry.get("opacity_image"):
                    continue
                entry["opacity_image"].save()

        for entry in baked_entries:
            if not entry:
                continue
            _build_baked_material(
                entry["material"],
                entry.get("base_image"),
                entry.get("opacity_image") if entry.get("use_opacity") else None,
                entry.get("use_opacity", False),
            )

    return result


def restore_baked_materials(result: BakeResult, keep_baked_materials: bool) -> None:
    """Restore original materials and clean up baked data blocks."""
    if keep_baked_materials:
        return

    for obj, materials in result.original_materials.items():
        for idx, mat in enumerate(materials):
            if idx >= len(obj.material_slots):
                continue
            obj.material_slots[idx].material = mat

    for mat in list(result.baked_materials):
        if mat.users == 0:
            try:
                bpy.data.materials.remove(mat)
            except Exception:
                pass

    for image in list(result.baked_images):
        if image.users == 0:
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass


def _resolve_bake_resolution(settings) -> int:
    value = getattr(settings, "bake_resolution", "2048")
    if value == 'CUSTOM':
        return int(getattr(settings, "bake_resolution_custom", 2048))
    try:
        return int(value)
    except Exception:
        return 2048


def _get_active_uv(obj) -> Optional[str]:
    uv_layers = getattr(obj.data, "uv_layers", None)
    if not uv_layers:
        return None
    active = uv_layers.active
    if active:
        return active.name
    if uv_layers:
        return uv_layers[0].name
    return None


def _material_needs_opacity(material) -> bool:
    if not material:
        return False
    if getattr(material, "blend_method", "OPAQUE") != "OPAQUE":
        return True
    if not material.use_nodes:
        color = getattr(material, "diffuse_color", None)
        if color and len(color) > 3:
            try:
                if float(color[3]) < 0.999:
                    return True
            except Exception:
                pass
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                alpha_socket = node.inputs.get('Alpha')
                if not alpha_socket:
                    continue
                if alpha_socket.is_linked:
                    return True
                try:
                    if float(alpha_socket.default_value) < 0.999:
                        return True
                except Exception:
                    continue
    return False


def _set_active_image_node(material, image, uv_layer: Optional[str]) -> None:
    nodes = material.node_tree.nodes
    node = nodes.new("ShaderNodeTexImage")
    node.image = image
    if uv_layer and hasattr(node, "uv_map"):
        node.uv_map = uv_layer
    nodes.active = node
    node.select = True


def _initialize_simple_material(baked_mat, source_mat) -> None:
    """Build a minimal node tree matching a non-node material."""
    nodes = baked_mat.node_tree.nodes
    links = baked_mat.node_tree.links
    nodes.clear()
    output_node = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])
    color = getattr(source_mat, "diffuse_color", (1.0, 1.0, 1.0, 1.0))
    try:
        principled.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
        principled.inputs['Alpha'].default_value = float(color[3]) if len(color) > 3 else 1.0
    except Exception:
        pass


def _configure_emission_for_alpha(material) -> None:
    """Route alpha into an Emission output for opacity baking."""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    output_node = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break
    if output_node is None:
        output_node = nodes.new("ShaderNodeOutputMaterial")

    for link in list(output_node.inputs['Surface'].links):
        links.remove(link)

    emission_node = nodes.new("ShaderNodeEmission")

    alpha_socket = None
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            alpha_socket = node.inputs.get('Alpha')
            break

    if alpha_socket and alpha_socket.is_linked:
        from_socket = alpha_socket.links[0].from_socket
        combine = nodes.new("ShaderNodeCombineRGB")
        links.new(from_socket, combine.inputs['R'])
        links.new(from_socket, combine.inputs['G'])
        links.new(from_socket, combine.inputs['B'])
        links.new(combine.outputs['Image'], emission_node.inputs['Color'])
    else:
        alpha_value = 1.0
        if alpha_socket:
            try:
                alpha_value = float(alpha_socket.default_value)
            except Exception:
                alpha_value = 1.0
        emission_node.inputs['Color'].default_value = (alpha_value, alpha_value, alpha_value, 1.0)

    links.new(emission_node.outputs['Emission'], output_node.inputs['Surface'])


def _build_baked_material(material, base_image, opacity_image, use_opacity: bool) -> None:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

    if base_image:
        base_node = nodes.new("ShaderNodeTexImage")
        base_node.image = base_image
        links.new(base_node.outputs['Color'], principled.inputs['Base Color'])

    if use_opacity and opacity_image:
        opacity_node = nodes.new("ShaderNodeTexImage")
        opacity_node.image = opacity_image
        try:
            separate = nodes.new("ShaderNodeSeparateColor")
            try:
                separate.mode = 'RGB'
            except Exception:
                pass
        except Exception:
            separate = nodes.new("ShaderNodeSeparateRGB")
        links.new(opacity_node.outputs['Color'], separate.inputs['Color'])
        links.new(separate.outputs['Red'], principled.inputs['Alpha'])
        material.blend_method = 'BLEND'
    else:
        material.blend_method = 'OPAQUE'


def _bake_object_pass(context, obj, bake_type: str, pass_filter: Optional[set], margin: int) -> None:
    if context.view_layer.objects.active != obj:
        context.view_layer.objects.active = obj
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    kwargs = {
        "type": bake_type,
        "margin": int(margin),
        "use_clear": True,
        "use_selected_to_active": False,
    }
    if pass_filter is not None:
        kwargs["pass_filter"] = pass_filter
    bpy.ops.object.bake(**kwargs)


def _select_object(context, obj) -> None:
    for selected in list(context.selected_objects):
        try:
            selected.select_set(False)
        except Exception:
            pass
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _create_bake_image(
    name: str,
    filepath: Path,
    width: int,
    height: int,
    colorspace: str,
) -> object:
    image = bpy.data.images.new(name=name, width=width, height=height, alpha=True)
    image.filepath_raw = str(filepath)
    image.file_format = "PNG"
    try:
        image.colorspace_settings.name = colorspace
    except Exception:
        pass
    return image


def _make_image_path(
    output_dir: Path,
    object_name: str,
    material_name: str,
    suffix: str,
    ext: str,
) -> Path:
    base = _safe_filename(f"{object_name}__{material_name}_{suffix}")
    filename = base + ext
    path = output_dir / filename
    counter = 1
    while path.exists():
        filename = f"{base}_{counter}{ext}"
        path = output_dir / filename
        counter += 1
    return path


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_\\-]+", "_", name.strip())
    return name.strip("_") or "baked"


def _unique_name(name: str, collection) -> str:
    if name not in collection:
        return name
    idx = 1
    while f"{name}_{idx}" in collection:
        idx += 1
    return f"{name}_{idx}"
