"""
Texture baking utilities for Bake Textures & Export.

Bakes base color and optional opacity textures per object/material.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import re
from contextlib import contextmanager

import bpy

from .materials.extract.core import material_has_transparency

_BAKE_IMAGE_FORMATS = {
    "AVIF": {
        "file_format": "AVIF",
        "extension": ".avif",
    },
    "PNG": {
        "file_format": "PNG",
        "extension": ".png",
    },
    "ORIGINAL": {
        "file_format": "ORIGINAL",
        "extension": "",
    },
}

_DEFAULT_BAKE_RESOLUTION = 2048
_DEFAULT_BAKE_IMAGE_FORMAT = "AVIF"
_DEFAULT_BAKE_MARGIN = 8


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

    bake_mode = str(getattr(settings, "bake_mode", "LIT_IBL") or "LIT_IBL")
    if bake_mode not in {"UNLIT_ALBEDO", "LIT_IBL"}:
        bake_mode = "LIT_IBL"

    resolution = _resolve_bake_resolution(settings)
    image_format = _resolve_bake_image_format(settings, diagnostics, safe_for_blender_save=True)
    margin = _resolve_bake_margin(settings)
    bake_base = bool(getattr(settings, "bake_base_color", True))
    bake_opacity = bool(getattr(settings, "bake_opacity", True))
    bake_roughness_map = (
        str(getattr(settings, "bake_mode", "LIT_IBL")) == "UNLIT_ALBEDO"
        and str(getattr(settings, "bake_unlit_mode", "UNLIT")) == "LIT_PBR"
    )
    isolate_meshes_lit = bool(getattr(settings, "bake_isolate_meshes_lit", False))
    roughness_single = (str(getattr(settings, "bake_roughness_mode", "TEXTURE")) == "AVERAGE")

    mesh_objects = [obj for obj in objects if getattr(obj, "type", None) == 'MESH']
    total_steps = 0
    if mesh_objects:
        for obj in mesh_objects:
            has_materials = any(slot.material for slot in obj.material_slots)
            if not has_materials:
                continue
            if bake_base:
                total_steps += 1
            if bake_roughness_map:
                total_steps += 1
            if bake_opacity:
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

    def _start_step(message: str) -> None:
        label = f"Step {completed_steps + 1}/{total_steps} - {message}"
        _report_progress(label)

    def _finish_step(message: str) -> None:
        nonlocal completed_steps
        completed_steps += 1
        _report_progress(f"Done {completed_steps}/{total_steps} - {message}")

    color_bake_type = 'DIFFUSE'
    color_pass_filter = {'COLOR'}
    if bake_mode == "LIT_IBL":
        color_bake_type = 'COMBINED'
        color_pass_filter = None

    with _temporary_ibl_world(context, settings, diagnostics, enabled=(bake_mode == "LIT_IBL")):
        mesh_count = len(mesh_objects)
        for mesh_index, obj in enumerate(mesh_objects, start=1):
            uv_layer_name = _get_active_uv(obj)
            if not uv_layer_name:
                msg = f"Bake failed: '{obj.name}' has no UV map."
                if diagnostics:
                    diagnostics.add_error(msg)
                raise RuntimeError(msg)

            _report_progress(f"Preparing bake targets [{mesh_index}/{mesh_count}] - {obj.name}")

            original_mats = [slot.material for slot in obj.material_slots]
            result.original_materials[obj] = original_mats

            baked_entries = []
            for slot in obj.material_slots:
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

                # Only short-circuit flat materials in UNLIT_ALBEDO, where the
                # baked texture would just be the constant color. In LIT_IBL the
                # bake captures lighting/shadows/AO onto every surface - including
                # flat-colored ones - so they must still be baked normally.
                flat_constants = (
                    _flat_material_constants(source_mat)
                    if bake_mode == "UNLIT_ALBEDO"
                    else None
                )
                mat_resolution = (
                    resolution
                    if resolution > 0
                    else _material_source_resolution(source_mat)
                )

                entry = {
                    "source_material": source_mat,
                    "material": baked_mat,
                    "base_image": None,
                    "opacity_image": None,
                    "merged_opacity_image": None,
                    "roughness_image": None,
                    "roughness_value": None,
                    "use_opacity": _material_needs_opacity(source_mat),
                    "uv_layer": uv_layer_name,
                    "flat": flat_constants,
                    "throwaway_image": None,
                    "resolution": mat_resolution,
                }

                if flat_constants is not None:
                    # Flat-color material: there is nothing texture-varying to bake,
                    # so skip baking entirely. Baking it would render a constant into
                    # a full-resolution texture (wasted file size) and, when the flat
                    # material's faces have no real UV unwrap, produce an all-black
                    # texture. The constant is authored directly in _build_baked_material.
                    #
                    # A whole-object bake still touches these faces when the object also
                    # has textured materials, and bpy.ops.object.bake errors on any slot
                    # without an active image node. Attach a tiny throwaway target to
                    # satisfy that requirement; it is never saved and is removed below.
                    throwaway = _create_bake_image(
                        name=f"{obj.name}_{baked_mat.name}_skipflat",
                        filepath=Path(""),
                        width=4,
                        height=4,
                        colorspace="sRGB",
                        file_format=image_format["file_format"],
                    )
                    entry["throwaway_image"] = throwaway
                    _set_active_image_node(baked_mat, throwaway, uv_layer_name)
                elif bake_base:
                    base_image_path = _make_image_path(
                        output_dir,
                        obj.name,
                        baked_mat.name,
                        "baseColor",
                        image_format["extension"],
                    )
                    base_image = _create_bake_image(
                        name=f"{obj.name}_{baked_mat.name}_baseColor",
                        filepath=base_image_path,
                        width=mat_resolution,
                        height=mat_resolution,
                        colorspace="sRGB",
                        file_format=image_format["file_format"],
                    )
                    entry["base_image"] = base_image
                    result.baked_images.append(base_image)
                    _set_active_image_node(baked_mat, base_image, uv_layer_name)

                baked_entries.append(entry)

            has_materials = any(entry for entry in baked_entries)
            has_base_targets = any(entry and entry.get("base_image") for entry in baked_entries)
            isolate_meshes = bake_mode == "LIT_IBL" and isolate_meshes_lit

            with _temporary_mesh_isolation(context, obj, enabled=isolate_meshes):
                if bake_base and has_base_targets:
                    label = "Baking material color" if bake_mode == "UNLIT_ALBEDO" else "Baking lighting and shadows"
                    step_message = f"{label} [{mesh_index}/{mesh_count}] - {obj.name}"
                    _start_step(step_message)
                    _select_object(context, obj)
                    # COMBINED (LIT_IBL) bakes real lighting and needs the user's
                    # samples; the albedo-only DIFFUSE/COLOR pass does not.
                    base_samples = None if bake_mode == "LIT_IBL" else 1
                    with _temporary_cycles_samples(context, base_samples):
                        _bake_object_pass(
                            context,
                            obj,
                            bake_type=color_bake_type,
                            pass_filter=color_pass_filter,
                            margin=margin,
                        )
                    for entry in baked_entries:
                        if not entry or not entry.get("base_image"):
                            continue
                        entry["base_image"].save()
                        if diagnostics:
                            diagnostics.add_generated_file(
                                "baked_base_color",
                                getattr(entry["base_image"], "filepath_raw", ""),
                                object=obj.name,
                                material=entry["source_material"].name,
                            )
                    _finish_step(step_message)

                if bake_roughness_map and has_materials:
                    step_message = f"Baking roughness [{mesh_index}/{mesh_count}] - {obj.name}"
                    _start_step(step_message)
                    if roughness_single:
                        # Averaged roughness only needs a tiny bake; cap at 64px.
                        # (resolution may be 0 here, the "use source resolution" sentinel.)
                        small_res = min(resolution, 64) if resolution > 0 else 64
                        for entry in baked_entries:
                            if not entry or entry.get("flat"):
                                continue
                            baked_mat = entry["material"]
                            rough_image = _create_bake_image(
                                name=f"{obj.name}_{baked_mat.name}_roughness",
                                filepath=Path(""),
                                width=small_res,
                                height=small_res,
                                colorspace="Non-Color",
                                file_format=image_format["file_format"],
                            )
                            entry["roughness_image"] = rough_image
                            _set_active_image_node(baked_mat, rough_image, entry["uv_layer"])

                        _select_object(context, obj)
                        with _temporary_cycles_samples(context, 1):
                            _bake_object_pass(
                                context,
                                obj,
                                bake_type='ROUGHNESS',
                                pass_filter=None,
                                margin=margin,
                            )
                        for entry in baked_entries:
                            if not entry or not entry.get("roughness_image"):
                                continue
                            rough_image = entry["roughness_image"]
                            entry["roughness_value"] = _average_image_value(rough_image)
                            entry["roughness_image"] = None
                            ## Force-remove the throwaway roughness bake image. A texture
                            ## node still references it here, so the old users==0 guard never
                            ## fired and leaked images with an empty ("." ) filepath into
                            ## bpy.data, which breaks downstream texture staging.
                            try:
                                bpy.data.images.remove(rough_image, do_unlink=True)
                            except Exception:
                                pass
                    else:
                        for entry in baked_entries:
                            if not entry or entry.get("flat"):
                                continue
                            baked_mat = entry["material"]
                            rough_image_path = _make_image_path(
                                output_dir,
                                obj.name,
                                baked_mat.name,
                                "roughness",
                                image_format["extension"],
                            )
                            rough_image = _create_bake_image(
                                name=f"{obj.name}_{baked_mat.name}_roughness",
                                filepath=rough_image_path,
                                width=entry["resolution"],
                                height=entry["resolution"],
                                colorspace="Non-Color",
                                file_format=image_format["file_format"],
                            )
                            entry["roughness_image"] = rough_image
                            result.baked_images.append(rough_image)
                            _set_active_image_node(baked_mat, rough_image, entry["uv_layer"])

                        _select_object(context, obj)
                        with _temporary_cycles_samples(context, 1):
                            _bake_object_pass(
                                context,
                                obj,
                                bake_type='ROUGHNESS',
                                pass_filter=None,
                                margin=margin,
                            )
                        for entry in baked_entries:
                            if not entry or not entry.get("roughness_image"):
                                continue
                            entry["roughness_image"].save()
                            if diagnostics:
                                diagnostics.add_generated_file(
                                    "baked_roughness",
                                    getattr(entry["roughness_image"], "filepath_raw", ""),
                                    object=obj.name,
                                    material=entry["source_material"].name,
                                )
                    _finish_step(step_message)

                if bake_opacity and has_materials:
                    step_message = f"Baking opacity [{mesh_index}/{mesh_count}] - {obj.name}"
                    _start_step(step_message)
                    for entry in baked_entries:
                        if not entry or entry.get("flat"):
                            continue
                        baked_mat = entry["material"]
                        opacity_image_path = _make_image_path(
                            output_dir,
                            obj.name,
                            baked_mat.name,
                            "opacity",
                            image_format["extension"],
                        )
                        opacity_image = _create_bake_image(
                            name=f"{obj.name}_{baked_mat.name}_opacity",
                            filepath=opacity_image_path,
                            # Must match the base image so opacity can be merged into its alpha.
                            width=entry["resolution"],
                            height=entry["resolution"],
                            colorspace="Non-Color",
                            file_format=image_format["file_format"],
                        )
                        entry["opacity_image"] = opacity_image
                        result.baked_images.append(opacity_image)
                        _set_active_image_node(baked_mat, opacity_image, entry["uv_layer"])
                        _configure_emission_for_alpha(baked_mat)

                    _select_object(context, obj)
                    with _temporary_cycles_samples(context, 1):
                        _bake_object_pass(
                            context,
                            obj,
                            bake_type='EMIT',
                            pass_filter=None,
                            margin=margin,
                        )
                    for entry in baked_entries:
                        if not entry or not entry.get("opacity_image"):
                            continue
                        entry["opacity_image"].save()
                        if diagnostics:
                            diagnostics.add_generated_file(
                                "baked_opacity",
                                getattr(entry["opacity_image"], "filepath_raw", ""),
                                object=obj.name,
                                material=entry["source_material"].name,
                            )
                    _finish_step(step_message)

                    for entry in baked_entries:
                        if not entry or entry.get("flat"):
                            continue
                        if not entry.get("use_opacity"):
                            continue
                        merged = _merge_opacity_into_base_image(
                            entry.get("base_image"),
                            entry.get("opacity_image"),
                        )
                        if merged:
                            entry["merged_opacity_image"] = entry.get("opacity_image")
                            entry["opacity_image"] = None

            for entry in baked_entries:
                if not entry:
                    continue
                # Remove the flat-slot throwaway target before authoring the final
                # material. It is only needed to satisfy the whole-object bake (now
                # finished) and is not tracked in result.baked_images, so doing this
                # first guarantees it can't leak if _build_baked_material raises.
                throwaway_image = entry.get("throwaway_image")
                if throwaway_image is not None:
                    try:
                        bpy.data.images.remove(throwaway_image, do_unlink=True)
                    except Exception:
                        pass
                    entry["throwaway_image"] = None
                _build_baked_material(
                    entry["material"],
                    entry.get("base_image"),
                    entry.get("opacity_image") if entry.get("use_opacity") else None,
                    entry.get("use_opacity", False),
                    uv_layer=entry.get("uv_layer"),
                    roughness_image=entry.get("roughness_image"),
                    roughness_value=entry.get("roughness_value"),
                    flat=entry.get("flat"),
                )
                merged_opacity_image = entry.get("merged_opacity_image")
                if merged_opacity_image is not None and getattr(merged_opacity_image, "users", 0) == 0:
                    try:
                        bpy.data.images.remove(merged_opacity_image)
                    except Exception:
                        pass

    return result


@contextmanager
def _temporary_ibl_world(context, settings, diagnostics=None, enabled: bool = True):
    """Temporarily override the scene World with a known IBL (HDRI) setup."""
    if not enabled:
        yield
        return

    source = str(getattr(settings, "bake_ibl_source", "SCENE_WORLD") or "SCENE_WORLD")
    if source != "HDRI_FILE":
        yield
        return

    hdri_path = str(getattr(settings, "bake_ibl_filepath", "") or "").strip()
    if not hdri_path:
        msg = "Bake mode is 'Lighting & Shadows' but no HDRI file is set."
        if diagnostics:
            diagnostics.add_error(msg)
        raise RuntimeError(msg)

    hdri_file = Path(hdri_path)
    if not hdri_file.exists():
        msg = f"HDRI file not found: {hdri_path}"
        if diagnostics:
            diagnostics.add_error(msg)
        raise RuntimeError(msg)

    strength = float(getattr(settings, "bake_ibl_strength", 1.0))
    rotation = float(getattr(settings, "bake_ibl_rotation", 0.0))  # stored in radians (ANGLE subtype)

    scene = context.scene
    original_world = scene.world
    temp_world = None
    try:
        temp_world = _create_hdri_world(hdri_path, strength, rotation)
        scene.world = temp_world
        yield
    finally:
        try:
            scene.world = original_world
        except Exception:
            pass
        if temp_world is not None:
            try:
                bpy.data.worlds.remove(temp_world)
            except Exception:
                pass


@contextmanager
def _temporary_cycles_samples(context, samples: Optional[int]):
    """Temporarily override Cycles bake sample count (and denoising).

    Property bakes - albedo (DIFFUSE/COLOR), roughness and opacity (EMIT) - are
    deterministic: their result is identical at 1 sample as at 64, so the scene's
    sample count is pure wasted render time on those passes. Only the LIT_IBL
    COMBINED pass bakes path-traced lighting and genuinely needs samples, so it
    passes ``samples=None`` to leave the user's setting untouched.
    """
    if samples is None:
        yield
        return

    cycles = getattr(context.scene, "cycles", None)
    if cycles is None:
        yield
        return

    original_samples = getattr(cycles, "samples", None)
    original_denoising = getattr(cycles, "use_denoising", None)
    try:
        try:
            cycles.samples = int(samples)
        except Exception:
            pass
        try:
            cycles.use_denoising = False
        except Exception:
            pass
        yield
    finally:
        if original_samples is not None:
            try:
                cycles.samples = original_samples
            except Exception:
                pass
        if original_denoising is not None:
            try:
                cycles.use_denoising = original_denoising
            except Exception:
                pass


@contextmanager
def _temporary_mesh_isolation(context, target_obj, enabled: bool = False):
    """Temporarily hide non-target meshes while baking a target object."""
    if not enabled:
        yield
        return

    hidden_states = []
    for obj in list(context.view_layer.objects):
        if obj == target_obj or getattr(obj, "type", None) != "MESH":
            continue
        try:
            hidden_states.append((obj, bool(obj.hide_viewport), bool(obj.hide_render)))
            obj.hide_viewport = True
            obj.hide_render = True
        except Exception:
            continue

    try:
        yield
    finally:
        for obj, old_hide_viewport, old_hide_render in hidden_states:
            try:
                obj.hide_viewport = old_hide_viewport
                obj.hide_render = old_hide_render
            except Exception:
                continue


def _create_hdri_world(hdri_path: str, strength: float, rotation_z: float):
    """Create a World datablock with an Environment Texture IBL."""
    world = bpy.data.worlds.new(name=_unique_name("BlenderToRCP_IBL", bpy.data.worlds))
    world.use_nodes = True
    nt = world.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    out.location = (600, 0)

    bg = nodes.new("ShaderNodeBackground")
    bg.location = (360, 0)
    try:
        bg.inputs["Strength"].default_value = strength
    except Exception:
        pass

    env = nodes.new("ShaderNodeTexEnvironment")
    env.location = (0, 0)
    try:
        env.image = bpy.data.images.load(hdri_path, check_existing=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to load HDRI image: {hdri_path} ({exc})") from exc

    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-240, 0)
    try:
        mapping.inputs["Rotation"].default_value[2] = rotation_z
    except Exception:
        pass

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-480, 0)

    try:
        links.new(texcoord.outputs.get("Generated"), mapping.inputs.get("Vector"))
    except Exception:
        pass
    try:
        links.new(mapping.outputs.get("Vector"), env.inputs.get("Vector"))
    except Exception:
        pass
    try:
        links.new(env.outputs.get("Color"), bg.inputs.get("Color"))
    except Exception:
        pass
    try:
        links.new(bg.outputs.get("Background"), out.inputs.get("Surface"))
    except Exception:
        pass

    return world


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
        try:
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        except (ReferenceError, Exception):
            pass

    for image in list(result.baked_images):
        try:
            if image.users == 0:
                bpy.data.images.remove(image)
        except (ReferenceError, Exception):
            pass


def _resolve_bake_resolution(settings) -> int:
    # Returns a fixed bake resolution in pixels, or 0 meaning "use each
    # material's own source-texture resolution" (resolved per material at
    # bake time by _material_source_resolution).
    #
    # When texture overrides are off (the default), we bake at the source
    # resolution rather than forcing 2048 - a 1K material should stay 1K
    # instead of being upscaled to 2K (slower bakes, 4x larger files).
    if not _export_texture_settings_enabled(settings):
        return 0

    value = getattr(settings, "bake_resolution", "2048")
    if str(value).upper() == "ORIGINAL":
        return 0
    if value == 'CUSTOM':
        return int(getattr(settings, "bake_resolution_custom", _DEFAULT_BAKE_RESOLUTION))
    try:
        return int(value)
    except Exception:
        return _DEFAULT_BAKE_RESOLUTION


_BAKED_CHANNEL_INPUTS = ("Base Color", "Roughness", "Alpha")


def _material_source_resolution(material, fallback: int = _DEFAULT_BAKE_RESOLUTION) -> int:
    """Largest source-texture dimension feeding the baked channels, or *fallback*.

    Used when baking at "original" resolution so each material's baked maps
    match the size of the textures it was authored with, rather than a global
    default. Only images that actually drive the channels we bake (base color,
    roughness, alpha) are considered - traced upstream from those Principled
    inputs. Maps we do not bake (e.g. a high-res normal map) and disconnected
    texture nodes are ignored, so a 1K albedo is not upscaled just because some
    other input uses a 4K texture. Falls back when no such image is found or
    its size is unknown (e.g. a procedural-only or unloaded texture).
    """
    if not getattr(material, "use_nodes", False) or material.node_tree is None:
        return fallback

    principled = next(
        (node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'),
        None,
    )
    if principled is None:
        return fallback

    stack = [
        principled.inputs[name]
        for name in _BAKED_CHANNEL_INPUTS
        if principled.inputs.get(name) is not None and principled.inputs[name].is_linked
    ]
    visited = set()
    largest = 0
    while stack:
        socket = stack.pop()
        for link in socket.links:
            node = link.from_node
            if node in visited:
                continue
            visited.add(node)
            if node.type == 'TEX_IMAGE':
                image = getattr(node, "image", None)
                size = tuple(getattr(image, "size", ()) or ())
                for dimension in size[:2]:
                    if dimension and dimension > largest:
                        largest = int(dimension)
            else:
                stack.extend(inp for inp in node.inputs if inp.is_linked)
    return largest if largest > 0 else fallback


def _resolve_texture_override_resolution(settings) -> int:
    if not _export_texture_settings_enabled(settings):
        return _DEFAULT_BAKE_RESOLUTION

    value = getattr(settings, "bake_resolution", "2048")
    if str(value).upper() == "ORIGINAL":
        return 0
    if value == 'CUSTOM':
        return int(getattr(settings, "bake_resolution_custom", _DEFAULT_BAKE_RESOLUTION))
    try:
        return int(value)
    except Exception:
        return _DEFAULT_BAKE_RESOLUTION


def _resolve_bake_image_format(settings, diagnostics=None, *, safe_for_blender_save: bool = False) -> Dict[str, str]:
    if _export_texture_settings_enabled(settings):
        requested = str(getattr(settings, "bake_image_format", _DEFAULT_BAKE_IMAGE_FORMAT) or _DEFAULT_BAKE_IMAGE_FORMAT).upper()
    else:
        requested = _DEFAULT_BAKE_IMAGE_FORMAT
    if requested not in _BAKE_IMAGE_FORMATS:
        requested = _DEFAULT_BAKE_IMAGE_FORMAT

    if requested == "ORIGINAL":
        if safe_for_blender_save:
            message = (
                "Original texture format is only available for existing texture staging; "
                "baked textures are saved as PNG."
            )
            print(f"Warning: {message}")
            if diagnostics:
                diagnostics.add_warning(message)
            requested = "PNG"
        else:
            return dict(_BAKE_IMAGE_FORMATS["ORIGINAL"])

    if safe_for_blender_save and requested == "AVIF":
        fallback = "PNG"
        message = (
            "AVIF baked textures are temporarily saved as PNG because Blender 5.1 RC's native AVIF "
            "image writer can crash during Image.save()."
        )
        print(f"Warning: {message}")
        if diagnostics:
            diagnostics.add_warning(message)
        requested = fallback

    available = _available_image_file_formats()
    if available and requested not in available:
        fallback = "PNG"
        if requested == "AVIF":
            message = (
                "AVIF baked textures require Blender 5.1 or newer; "
                f"this Blender build does not support AVIF image saving, falling back to '{fallback}'."
            )
            print(f"Warning: {message}")
            if diagnostics:
                diagnostics.add_warning(message)
        elif diagnostics:
            diagnostics.add_warning(
                f"Bake image format '{requested}' is not supported by this Blender build; falling back to '{fallback}'."
            )
        requested = fallback

    return dict(_BAKE_IMAGE_FORMATS[requested])


def _resolve_bake_margin(settings) -> int:
    if not _export_texture_settings_enabled(settings):
        return _DEFAULT_BAKE_MARGIN
    try:
        return int(getattr(settings, "bake_margin", _DEFAULT_BAKE_MARGIN))
    except Exception:
        return _DEFAULT_BAKE_MARGIN


def _export_texture_settings_enabled(settings) -> bool:
    return bool(getattr(settings, "export_texture_settings_enabled", False))


def _available_image_file_formats() -> Optional[set[str]]:
    try:
        prop = bpy.types.Image.bl_rna.properties["file_format"]
        return {item.identifier for item in prop.enum_items}
    except Exception:
        return None


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


def _flat_material_constants(material) -> Optional[Dict[str, object]]:
    """Return constant PBR values when *material* is a flat-color material.

    A material is "flat" when nothing texture-varying feeds its surface: it has
    no image-texture nodes and its Principled Base Color is an unlinked constant.
    Such materials must not be baked - baking would burn a single color into a
    full-resolution texture (wasted file size) and, when the faces have no real
    UV unwrap, yields an all-black texture. Instead the returned constants are
    authored directly so apps like Reality Composer Pro show the exact color.

    Returns ``None`` for any material that genuinely needs a texture bake.
    """
    if not getattr(material, "use_nodes", False) or material.node_tree is None:
        # Non-node material: its only color is the legacy diffuse_color.
        color = getattr(material, "diffuse_color", (0.8, 0.8, 0.8, 1.0))
        alpha = float(color[3]) if len(color) > 3 else 1.0
        return {
            "base_color": (color[0], color[1], color[2], alpha),
            "roughness": float(getattr(material, "roughness", 0.5)),
            "metallic": float(getattr(material, "metallic", 0.0)),
            "alpha": alpha,
        }

    node_tree = material.node_tree
    # Any image texture means there is something worth baking.
    if any(node.type == 'TEX_IMAGE' for node in node_tree.nodes):
        return None

    principled = next(
        (node for node in node_tree.nodes if node.type == 'BSDF_PRINCIPLED'),
        None,
    )
    if principled is None:
        return None

    base_color = principled.inputs.get('Base Color')
    if base_color is None or base_color.is_linked:
        return None

    base = tuple(base_color.default_value)
    base_rgba = (base[0], base[1], base[2], base[3] if len(base) > 3 else 1.0)

    roughness = principled.inputs.get('Roughness')
    metallic = principled.inputs.get('Metallic')
    alpha = principled.inputs.get('Alpha')

    return {
        "base_color": base_rgba,
        "roughness": float(roughness.default_value)
        if roughness is not None and not roughness.is_linked
        else None,
        "metallic": float(metallic.default_value)
        if metallic is not None and not metallic.is_linked
        else None,
        "alpha": float(alpha.default_value)
        if alpha is not None and not alpha.is_linked
        else 1.0,
    }


def _material_needs_opacity(material) -> bool:
    # Detect transparency from the real Alpha input. ``blend_method`` is a
    # deprecated alias on Blender 4.2+/5.x that never reports OPAQUE, so it
    # cannot be used to decide whether a material actually needs an opacity bake.
    return material_has_transparency(material)


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
        combine, inputs, output = _new_combine_color_node(nodes)
        for input_name in inputs:
            links.new(from_socket, combine.inputs[input_name])
        links.new(combine.outputs[output], emission_node.inputs['Color'])
    else:
        alpha_value = 1.0
        if alpha_socket:
            try:
                alpha_value = float(alpha_socket.default_value)
            except Exception:
                alpha_value = 1.0
        emission_node.inputs['Color'].default_value = (alpha_value, alpha_value, alpha_value, 1.0)

    links.new(emission_node.outputs['Emission'], output_node.inputs['Surface'])


def _average_image_value(image) -> float:
    try:
        px = image.pixels[:]
    except Exception:
        return 0.5
    count = len(px) // 4
    if count <= 0:
        return 0.5
    step = max(1, count // 4096)
    total = 0.0
    n = 0
    for i in range(0, count, step):
        total += px[i * 4]
        n += 1
    return (total / n) if n else 0.5


def _new_combine_color_node(nodes):
    """Create a shader color-combine node across Blender versions."""
    try:
        return nodes.new("ShaderNodeCombineColor"), ("Red", "Green", "Blue"), "Color"
    except Exception:
        return nodes.new("ShaderNodeCombineRGB"), ("R", "G", "B"), "Image"


def _build_baked_material(
    material,
    base_image,
    opacity_image,
    use_opacity: bool,
    *,
    uv_layer: Optional[str] = None,
    roughness_image=None,
    roughness_value=None,
    flat: Optional[Dict[str, object]] = None,
) -> None:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

    if flat is not None:
        # Flat-color material: author the captured constants directly (no textures),
        # so the exported USD carries the exact color/roughness/metallic.
        base = flat.get("base_color", (0.8, 0.8, 0.8, 1.0))
        try:
            principled.inputs['Base Color'].default_value = (base[0], base[1], base[2], 1.0)
        except Exception:
            pass
        if flat.get("roughness") is not None:
            try:
                principled.inputs['Roughness'].default_value = float(flat["roughness"])
            except Exception:
                pass
        if flat.get("metallic") is not None:
            try:
                principled.inputs['Metallic'].default_value = float(flat["metallic"])
            except Exception:
                pass
        alpha_value = float(flat.get("alpha", 1.0))
        try:
            principled.inputs['Alpha'].default_value = alpha_value
        except Exception:
            pass
        material.blend_method = 'BLEND' if (use_opacity and alpha_value < 1.0) else 'OPAQUE'
        return

    if roughness_image is not None:
        rough_node = nodes.new("ShaderNodeTexImage")
        rough_node.image = roughness_image
        if uv_layer and hasattr(rough_node, "uv_map"):
            rough_node.uv_map = uv_layer
        links.new(rough_node.outputs['Color'], principled.inputs['Roughness'])
    elif roughness_value is not None:
        try:
            principled.inputs['Roughness'].default_value = float(roughness_value)
        except Exception:
            pass

    if base_image:
        base_node = nodes.new("ShaderNodeTexImage")
        base_node.image = base_image
        if uv_layer and hasattr(base_node, "uv_map"):
            base_node.uv_map = uv_layer
        links.new(base_node.outputs['Color'], principled.inputs['Base Color'])
        if use_opacity and opacity_image is None:
            alpha_output = base_node.outputs.get('Alpha')
            if alpha_output is not None:
                links.new(alpha_output, principled.inputs['Alpha'])
                material.blend_method = 'BLEND'
                return

    if use_opacity and opacity_image:
        opacity_node = nodes.new("ShaderNodeTexImage")
        opacity_node.image = opacity_image
        if uv_layer and hasattr(opacity_node, "uv_map"):
            opacity_node.uv_map = uv_layer
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


def _merge_opacity_into_base_image(base_image, opacity_image) -> bool:
    """Copy a grayscale opacity bake into the alpha channel of the base image."""
    if base_image is None or opacity_image is None:
        return False

    try:
        base_size = tuple(getattr(base_image, "size", ())[:2])
        opacity_size = tuple(getattr(opacity_image, "size", ())[:2])
    except Exception:
        return False

    if len(base_size) != 2 or len(opacity_size) != 2 or base_size != opacity_size:
        return False

    try:
        base_pixels = list(base_image.pixels)
        opacity_pixels = list(opacity_image.pixels)
    except Exception:
        return False

    if len(base_pixels) != len(opacity_pixels):
        return False

    for idx in range(0, len(base_pixels), 4):
        base_pixels[idx + 3] = opacity_pixels[idx]

    try:
        base_image.pixels[:] = base_pixels
        base_image.save()
    except Exception:
        return False

    opacity_path = getattr(opacity_image, "filepath_raw", "") or ""
    if not opacity_path:
        return True

    try:
        opacity_file = Path(opacity_path)
        if opacity_file.exists():
            opacity_file.unlink()
    except Exception:
        pass
    return True


def _bake_object_pass(
    context,
    obj,
    bake_type: str,
    pass_filter: Optional[set],
    margin: int,
    **extra_kwargs,
) -> None:
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
    kwargs.update(extra_kwargs)
    try:
        bpy.ops.object.bake(**kwargs)
    except TypeError:
        # Some Blender builds don't expose every bake option; retry with the baseline args.
        for key in list(extra_kwargs.keys()):
            kwargs.pop(key, None)
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
    file_format: str,
) -> object:
    image = bpy.data.images.new(name=name, width=width, height=height, alpha=True)
    image.filepath_raw = str(filepath)
    try:
        image.file_format = file_format
    except Exception:
        image.filepath_raw = str(filepath.with_suffix(".png"))
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
