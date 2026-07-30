"""
Blender material extraction for RealityKit export.

Extracts supported parameters and emits warnings for unsupported nodes.
"""

import hashlib
import os
import re
import shutil
import tempfile
from array import array
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ....manifest.materialx_nodes import load_manifest, select_nodedef_name_for_node
from ..graph import texture_colorspace_role

_MANIFEST_CACHE: Optional[Dict[str, Any]] = None
_STAGED_IMAGE_CACHE: Dict[Any, str] = {}
_STAGED_IMAGE_DIR: Optional[Path] = None
_STAGED_IMAGE_DIR_OWNED = False

# Blender 5.2 no longer has a material render mode that means "alpha clip".
# A RealityKit opacityThreshold is therefore authored only when the scene opts
# into this exporter contract with an explicit, finite threshold value.
_ALPHA_CUTOUT_THRESHOLD_PROPERTY = "blender_to_rcp_alpha_cutout_threshold"

_FORMAT_TO_EXTENSION = {
    "AVIF": ".avif",
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPG": ".jpg",
    "TIFF": ".tif",
    "TIF": ".tif",
    "TARGA": ".tga",
    "TARGA_RAW": ".tga",
    "OPEN_EXR": ".exr",
    "OPEN_EXR_MULTILAYER": ".exr",
    "HDR": ".hdr",
    "BMP": ".bmp",
    "WEBP": ".webp",
}

_EXTENSION_TO_FORMAT = {
    ".avif": "AVIF",
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".tga": "TARGA",
    ".exr": "OPEN_EXR",
    ".hdr": "HDR",
    ".bmp": "BMP",
    ".webp": "WEBP",
}


def material_has_transparency(material) -> bool:
    """True when a material's alpha actually produces transparency.

    Blender 5.2's ``surface_render_method`` chooses how Eevee renders
    transparency; it does not say whether the active surface contains any.
    Transparency must be read from the real Alpha input instead.
    """
    if not material:
        return False
    if not getattr(material, "use_nodes", False):
        color = getattr(material, "diffuse_color", None)
        if color is not None and len(color) > 3:
            try:
                return float(color[3]) < 0.999
            except (TypeError, ValueError):
                return False
        return False
    node_tree = getattr(material, "node_tree", None)
    if not node_tree:
        return False
    # Only the shader connected to the active Material Output contributes to
    # rendering. Disconnected Principled nodes must not make an opaque material
    # transparent or disagree with the bake pipeline.
    surface_node = _get_surface_shader_node(material)
    if not surface_node or surface_node.type != 'BSDF_PRINCIPLED':
        return False
    alpha_socket = surface_node.inputs.get('Alpha')
    if not alpha_socket:
        return False
    if alpha_socket.is_linked:
        return True
    try:
        return float(alpha_socket.default_value) < 0.999
    except (TypeError, ValueError):
        return False


def opacity_threshold_from_material(
    material,
    is_transparent: bool,
) -> Optional[float]:
    """Return an explicit RealityKit alpha-cutout threshold, if present.

    Blender 5.2 exposes only ``DITHERED`` and ``BLENDED`` surface render
    methods. Neither is a cutout declaration, so render method must never imply
    a hard threshold. Scenes that intentionally want a RealityKit cutout can
    set ``blender_to_rcp_alpha_cutout_threshold`` to a finite value in [0, 1].
    A boolean flag is deliberately insufficient: without a numeric threshold
    there is no complete cutout contract to export.
    """
    if not is_transparent:
        return None
    try:
        value = material.get(_ALPHA_CUTOUT_THRESHOLD_PROPERTY)
    except Exception:
        return None
    if value is None or isinstance(value, bool):
        return None
    try:
        threshold = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (0.0 <= threshold <= 1.0):
        return None
    return threshold


def should_author_opacity_threshold(material, is_transparent: bool) -> bool:
    """Whether the explicit BlenderToRCP alpha-cutout contract is complete."""
    return opacity_threshold_from_material(material, is_transparent) is not None


def extract_blender_material_data(material) -> Dict[str, Any]:
    """Extract supported material parameters from a Blender material."""
    data = {
        'name': material.name,
        'type': 'unknown',
    }
    data['surface_render_method'] = getattr(
        material,
        "surface_render_method",
        "DITHERED",
    )
    data['is_transparent'] = material_has_transparency(material)

    if not material.use_nodes:
        data['type'] = 'simple'
        data['base_color'] = list(material.diffuse_color)[:3]
        data['alpha'] = material.diffuse_color[3] if len(material.diffuse_color) > 3 else 1.0
        return data

    surface_node = _get_surface_shader_node(material)
    if surface_node and surface_node.type == 'GROUP':
        node_tree = getattr(surface_node, "node_tree", None)
        node_id = node_tree.get("rk_node_id") if node_tree else None
        node_name = (node_tree.name or "").lstrip(".") if node_tree else ""
        if node_id or (node_tree and node_name.startswith("RK_")):
            return _extract_rk_group_material_data(surface_node, data)

    if surface_node and surface_node.type == 'BSDF_PRINCIPLED':
        principled = surface_node
    else:
        principled = None

    if principled:
        data['type'] = 'principled'
        resolve_cache = {}
        unresolved_warnings: List[str] = []
        input_graphs: Dict[str, Any] = {}

        graph_input_map = {
            'Base Color': 'baseColor',
            'Metallic': 'metallic',
            'Roughness': 'roughness',
            'Specular IOR Level': '_specularLevel',
            'Normal': 'normal',
            'Alpha': 'opacity',
            'Emission Color': '_emissionColor',
            'Emission Strength': '_emissionStrength',
            'Diffuse Roughness': 'baseDiffuseRoughness',
            'Subsurface Weight': 'subsurfaceWeight',
            'Subsurface Radius': 'subsurfaceRadiusScale',
            'Subsurface Scale': 'subsurfaceRadius',
            'Subsurface Anisotropy': 'subsurfaceScatterAnisotropy',
            'IOR': 'specularIOR',
            'Specular Tint': 'specularColor',
            'Anisotropic': 'specularAnisotropyLevel',
            'Anisotropic Rotation': 'specularAnisotropyAngle',
            'Coat IOR': 'clearcoatIOR',
            'Sheen Weight': '_sheenWeight',
            'Sheen Roughness': '_sheenRoughness',
            'Sheen Tint': '_sheenTint',
        }
        expected_type_map = {
            'Base Color': 'color3',
            'Metallic': 'float',
            'Roughness': 'float',
            'Specular IOR Level': 'float',
            'Normal': 'vector3',
            'Alpha': 'float',
            'Emission Color': 'color3',
            'Emission Strength': 'float',
            'Diffuse Roughness': 'float',
            'Subsurface Weight': 'float',
            'Subsurface Radius': 'color3',
            'Subsurface Scale': 'float',
            'Subsurface Anisotropy': 'float',
            'IOR': 'float',
            'Specular Tint': 'color3',
            'Anisotropic': 'float',
            'Anisotropic Rotation': 'float',
            'Coat IOR': 'float',
            'Sheen Weight': 'float',
            'Sheen Roughness': 'float',
            'Sheen Tint': 'color3',
        }

        base_color_socket = principled.inputs.get('Base Color')
        metallic_socket = principled.inputs.get('Metallic')
        roughness_socket = principled.inputs.get('Roughness')
        specular_socket = principled.inputs.get('Specular IOR Level')
        alpha_socket = principled.inputs.get('Alpha')

        if base_color_socket:
            data['base_color'] = list(base_color_socket.default_value)[:3]
        if metallic_socket:
            data['metallic'] = metallic_socket.default_value
        if roughness_socket:
            data['roughness'] = roughness_socket.default_value
        if specular_socket:
            data['specular'] = specular_socket.default_value
        if alpha_socket:
            data['alpha'] = alpha_socket.default_value

        emission_color_socket = principled.inputs.get('Emission Color')
        emission_strength_socket = principled.inputs.get('Emission Strength')
        if emission_color_socket:
            data['emission_color'] = list(emission_color_socket.default_value)[:3]
        if emission_strength_socket and not emission_strength_socket.is_linked:
            data['emission_strength'] = emission_strength_socket.default_value

        clearcoat_socket = principled.inputs.get('Coat Weight')
        clearcoat_roughness_socket = principled.inputs.get('Coat Roughness')
        if clearcoat_socket:
            data['clearcoat'] = clearcoat_socket.default_value
        if clearcoat_roughness_socket:
            data['clearcoat_roughness'] = clearcoat_roughness_socket.default_value

        pbr2_socket_map = {
            'Diffuse Roughness': ('diffuse_roughness', 'float'),
            'Subsurface Weight': ('subsurface_weight', 'float'),
            # Blender's scalar Scale is the physical radius; its RGB Radius is
            # the per-channel multiplier used by PBR2/OpenPBR.
            'Subsurface Scale': ('subsurface_radius', 'float'),
            'Subsurface Radius': ('subsurface_radius_scale', 'color'),
            'Subsurface Anisotropy': ('subsurface_anisotropy', 'float'),
            'IOR': ('ior', 'float'),
            'Specular Tint': ('specular_tint', 'color'),
            'Anisotropic': ('anisotropic', 'float'),
            'Anisotropic Rotation': ('anisotropic_rotation', 'float'),
            'Coat IOR': ('clearcoat_ior', 'float'),
            'Coat Tint': ('clearcoat_tint', 'color'),
            'Sheen Weight': ('sheen_weight', 'float'),
            'Sheen Roughness': ('sheen_roughness', 'float'),
            'Sheen Tint': ('sheen_tint', 'color'),
        }
        for socket_name, (data_name, value_kind) in pbr2_socket_map.items():
            socket = principled.inputs.get(socket_name)
            if socket is None or socket.is_linked:
                continue
            value = _socket_default_value(socket)
            if value is None:
                continue
            data[data_name] = _coerce_constant_value(value, value_kind)
        if 'sheen_weight' in data and 'sheen_tint' in data:
            data['sheen_color'] = [
                float(component) * float(data['sheen_weight'])
                for component in data['sheen_tint'][:3]
            ]
        if 'specular' in data:
            # Blender's default 0.5 multiplier corresponds to PBR2 weight 1.
            data['specular_weight'] = max(0.0, float(data['specular']) * 2.0)

        alpha_threshold = opacity_threshold_from_material(
            material,
            data['is_transparent'],
        )
        if alpha_threshold is not None:
            data['alpha_threshold'] = alpha_threshold

        # Bake Textures & Export can author AO as a baked texture without wiring it into the
        # Principled node graph. In that case we read it from custom properties.
        try:
            baked_ao = material.get("blender_to_rcp_ao_texture")
        except Exception:
            baked_ao = None
        if isinstance(baked_ao, str) and baked_ao:
            data['ao_texture'] = baked_ao
            try:
                baked_uv = material.get("blender_to_rcp_ao_uv")
            except Exception:
                baked_uv = None
            if isinstance(baked_uv, str) and baked_uv:
                data['ao_texture_texcoord'] = _normalize_uv_map_name(baked_uv)
            data['ao_texture_colorspace'] = 'Non-Color'

        texture_map = {
            'Base Color': 'base_color_texture',
            'Metallic': 'metallic_texture',
            'Roughness': 'roughness_texture',
            'Normal': 'normal_texture',
            'Alpha': 'alpha_texture',
            'Coat Normal': 'clearcoat_normal_texture',
            'Emission Color': 'emission_texture',
        }
        constant_map = {
            'Base Color': ('base_color', 'color'),
            'Metallic': ('metallic', 'float'),
            'Roughness': ('roughness', 'float'),
            'Specular IOR Level': ('specular', 'float'),
            'Alpha': ('alpha', 'float'),
            'Emission Color': ('emission_color', 'color'),
            'Emission Strength': ('emission_strength', 'float'),
            'Coat Weight': ('clearcoat', 'float'),
            'Coat Roughness': ('clearcoat_roughness', 'float'),
            'Diffuse Roughness': ('diffuse_roughness', 'float'),
            'Subsurface Weight': ('subsurface_weight', 'float'),
            'Subsurface Radius': ('subsurface_radius_scale', 'color'),
            'Subsurface Scale': ('subsurface_radius', 'float'),
            'Subsurface Anisotropy': ('subsurface_anisotropy', 'float'),
            'IOR': ('ior', 'float'),
            'Specular Tint': ('specular_tint', 'color'),
            'Anisotropic': ('anisotropic', 'float'),
            'Anisotropic Rotation': ('anisotropic_rotation', 'float'),
            'Coat IOR': ('clearcoat_ior', 'float'),
            'Coat Tint': ('clearcoat_tint', 'color'),
            'Sheen Weight': ('sheen_weight', 'float'),
            'Sheen Roughness': ('sheen_roughness', 'float'),
            'Sheen Tint': ('sheen_tint', 'color'),
        }
        for input_name, input_socket in principled.inputs.items():
            if not input_socket.is_linked:
                continue

            expected_type = expected_type_map.get(input_name)
            resolved = _resolve_socket_value(
                input_socket,
                cache=resolve_cache,
                expected_type=expected_type,
            )
            if resolved and resolved.get("kind") == "texture" and input_name in texture_map:
                texture_key = texture_map[input_name]
                data[texture_key] = resolved["path"]
                channel = resolved.get("channel")
                if channel:
                    data[f"{texture_key}_channel"] = channel
                uv_map = resolved.get("uv_map")
                if uv_map:
                    data[f"{texture_key}_texcoord"] = _normalize_uv_map_name(uv_map)
                mapping = resolved.get("mapping")
                if mapping:
                    data[f"{texture_key}_mapping"] = mapping
                colorspace = resolved.get("colorspace")
                if colorspace:
                    data[f"{texture_key}_colorspace"] = colorspace
                alpha_mode = resolved.get("alpha_mode")
                if alpha_mode:
                    data[f"{texture_key}_alpha_mode"] = alpha_mode
                scale = resolved.get("scale")
                if scale is not None:
                    data[f"{texture_key}_scale"] = scale
                space = resolved.get("space")
                if space:
                    data[f"{texture_key}_space"] = space
                if input_name == 'Base Color':
                    data.pop('base_color', None)
                    _record_base_color_texture_semantics(data, resolved)
                if resolved.get("current_pixel_snapshot"):
                    data['native_preview_stale'] = True
                continue

            if resolved and resolved.get("kind") == "texture":
                target_input = graph_input_map.get(input_name)
                if target_input:
                    input_graphs[target_input] = resolved
                    if resolved.get("current_pixel_snapshot"):
                        data['native_preview_stale'] = True
                    continue

            if resolved and resolved.get("kind") == "node":
                target_input = graph_input_map.get(input_name)
                if target_input:
                    input_graphs[target_input] = resolved
                    if input_name == 'Base Color':
                        _record_base_color_texture_semantics(data, resolved)
                    continue

            if resolved and resolved.get("kind") == "constant" and input_name in constant_map:
                key, expected = constant_map[input_name]
                data[key] = _coerce_constant_value(resolved["value"], expected)
                continue

            if resolved and resolved.get("kind") == "unresolved":
                chain = resolved.get("provenance") or []
                if chain:
                    reason = resolved.get("reason")
                    suffix = f" ({reason})" if reason else ""
                    unresolved_warnings.append(
                        f"Material '{material.name}': Unable to resolve '{input_name}' "
                        f"through chain: {' -> '.join(chain)}{suffix}"
                    )

            constant = _extract_constant_from_socket(input_socket)
            if constant is not None and input_name in constant_map:
                key, expected = constant_map[input_name]
                data[key] = _coerce_constant_value(constant, expected)

            from_node = input_socket.links[0].from_node
            if from_node.type == 'TEX_IMAGE' and 'ao' in from_node.name.lower():
                texture_path = _resolve_image_path(from_node.image)
                if texture_path:
                    data['ao_texture'] = texture_path

        if unresolved_warnings:
            data['unresolved_warnings'] = unresolved_warnings
        # Linked Blender constant nodes are folded during the loop above, so
        # recompute derived PBR2 controls after all sockets have resolved.
        if (
            '_sheenWeight' not in input_graphs
            and '_sheenTint' not in input_graphs
            and 'sheen_weight' in data
            and 'sheen_tint' in data
        ):
            data['sheen_color'] = [
                float(component) * float(data['sheen_weight'])
                for component in data['sheen_tint'][:3]
            ]
        if '_specularLevel' not in input_graphs and 'specular' in data:
            data['specular_weight'] = max(0.0, float(data['specular']) * 2.0)
        if '_sheenWeight' in input_graphs or '_sheenTint' in input_graphs:
            # Preserve the independent Blender controls until graph-profile
            # selection. PBR2 combines them into sheenColor, while OpenPBR has
            # distinct fuzz_weight/fuzz_color inputs.
            data.pop('sheen_color', None)
        if input_graphs:
            if any(_expression_has_current_pixel_snapshot(expr) for expr in input_graphs.values()):
                data['native_preview_stale'] = True
            data['input_graphs'] = input_graphs

    else:
        # Only the shader wired to the active Material Output contributes.
        # Never replace an unsupported active shader with an orphan Emission.
        emission_node = (
            surface_node
            if surface_node and surface_node.type == 'EMISSION'
            else None
        )

        if emission_node:
            data['type'] = 'emission'
            color_socket = emission_node.inputs.get('Color')
            strength_socket = emission_node.inputs.get('Strength')
            resolve_cache = {}
            color_expr = None
            strength_expr = _constant_expr(1.0)

            if color_socket:
                if color_socket.is_linked:
                    color_expr = _resolve_socket_value(
                        color_socket,
                        cache=resolve_cache,
                        expected_type='color3',
                    )
                else:
                    color_expr = _constant_expr(
                        _coerce_constant_value(_socket_default_value(color_socket), 'color')
                    )

            if strength_socket:
                if strength_socket.is_linked:
                    strength_expr = _resolve_socket_value(
                        strength_socket,
                        cache=resolve_cache,
                        expected_type='float',
                    )
                else:
                    strength_expr = _constant_expr(
                        _coerce_constant_value(_socket_default_value(strength_socket), 'float')
                    )

            unresolved = []
            if not color_expr or color_expr.get('kind') == 'unresolved':
                unresolved.append(
                    f"Material '{material.name}': standalone Emission Color requires baking; "
                    "the linked graph could not be resolved exactly."
                )
            if not strength_expr or strength_expr.get('kind') == 'unresolved':
                unresolved.append(
                    f"Material '{material.name}': standalone Emission Strength requires baking; "
                    "the linked graph could not be resolved exactly."
                )

            if unresolved:
                data['unresolved_warnings'] = unresolved
            elif color_expr.get('kind') == 'constant' and strength_expr.get('kind') == 'constant':
                color = _coerce_constant_value(color_expr.get('value'), 'color')
                strength = _coerce_constant_value(strength_expr.get('value'), 'float')
                data['base_color'] = [component * strength for component in color]
                data['emission_strength'] = strength
            else:
                if color_expr.get('kind') == 'texture':
                    color_expr = dict(color_expr)
                    color_expr['colorspace_role'] = 'color'
                if strength_expr.get('kind') == 'texture':
                    strength_expr = dict(strength_expr)
                    strength_expr['colorspace_role'] = 'data'

                if strength_expr.get('kind') == 'constant':
                    strength = _coerce_constant_value(strength_expr.get('value'), 'float')
                    if color_expr.get('kind') == 'texture':
                        color_expr = dict(color_expr)
                        color_expr['scale'] = strength
                        final_expr = color_expr
                    elif abs(strength - 1.0) <= 1e-6:
                        final_expr = color_expr
                    else:
                        strength_expr = _constant_expr(strength)
                        strength_color = _make_node_expr(
                            _nodedef_for('combine3', 'color3'),
                            {
                                'in1': strength_expr,
                                'in2': strength_expr,
                                'in3': strength_expr,
                            },
                        )
                        final_expr = _make_node_expr(
                            _nodedef_for('multiply', 'color3'),
                            {'in1': color_expr, 'in2': strength_color},
                        )
                else:
                    strength_color = _make_node_expr(
                        _nodedef_for('combine3', 'color3'),
                        {
                            'in1': strength_expr,
                            'in2': strength_expr,
                            'in3': strength_expr,
                        },
                    )
                    final_expr = _make_node_expr(
                        _nodedef_for('multiply', 'color3'),
                        {'in1': color_expr, 'in2': strength_color},
                    )
                data['input_graphs'] = {'color': final_expr}
                if _expression_has_current_pixel_snapshot(final_expr):
                    data['native_preview_stale'] = True

    return data


def collect_material_warnings(material) -> List[str]:
    """Collect warnings for Blender nodes unsupported by RealityKit export."""
    warnings: List[str] = []
    if not material or not material.use_nodes or not material.node_tree:
        return warnings

    used_nodes, volume_linked, displacement_linked = _collect_used_nodes(material)
    if volume_linked:
        warnings.append(
            f"Material '{material.name}': Volume output is not supported in RCP; bake or remove."
        )
    if displacement_linked:
        warnings.append(
            f"Material '{material.name}': Displacement output is not supported; bake geometry."
        )

    # Derived from the validator rather than a second hand-maintained list.
    # The local copy had drifted 14 entries behind - TEX_NOISE, CLAMP,
    # MAP_RANGE, REROUTE and others export correctly but were reported as
    # "unrecognized; export may differ", and INVERT as "requires baking",
    # directly contradicting what `validate` had just told the user about the
    # same material. The validator is the capability authority; this pass only
    # phrases the warnings.
    from ....nodes.validate import BAKE_TYPES as _VALIDATOR_BAKE_TYPES
    from ....nodes.validate import SUPPORTED_TYPES as _VALIDATOR_SUPPORTED_TYPES

    supported_types = set(_VALIDATOR_SUPPORTED_TYPES)

    partial_types = {
        'TEX_COORD',
        'UVMAP',
        'MAPPING',
    }

    bake_types = set(_VALIDATOR_BAKE_TYPES)

    unsupported_types = {
        'OUTPUT_AOV',
        'OUTPUT_WORLD',
        'OUTPUT_LIGHT',
        'BACKGROUND',
        'HOLDOUT',
        'MIX_SHADER',
        'ADD_SHADER',
        'BSDF_DIFFUSE',
        'BSDF_GLOSSY',
        'BSDF_GLASS',
        'BSDF_METALLIC',
        'BSDF_REFRACTION',
        'BSDF_SPECULAR',
        'BSDF_RAY_PORTAL',
        'BSDF_TRANSLUCENT',
        'BSDF_TRANSPARENT',
        'BSDF_SHEEN',
        'BSDF_VELVET',
        'BSDF_TOON',
        'SUBSURFACE_SCATTERING',
        'BSDF_HAIR',
        'BSDF_HAIR_PRINCIPLED',
        'PRINCIPLED_HAIR',
        'VOLUME_ABSORPTION',
        'VOLUME_SCATTER',
        'PRINCIPLED_VOLUME',
        'VOLUME_COEFFICIENTS',
        'GEOMETRY',
        'OBJECT_INFO',
        'CAMERA_DATA',
        'AMBIENT_OCCLUSION',
        'HAIR_INFO',
        'CURVE_INFO',
        'PARTICLE_INFO',
        'POINT_INFO',
        'VERTEX_COLOR',
        'VOLUME_INFO',
        'WIREFRAME',
        'LIGHT_PATH',
        'FRESNEL',
        'LAYER_WEIGHT',
        'TANGENT',
        'BEVEL',
        'ATTRIBUTE',
    }

    for node in used_nodes:
        node_type = getattr(node, "type", "")
        node_name = getattr(node, "name", node_type)

        if node_type == 'GROUP':
            node_tree = getattr(node, "node_tree", None)
            node_id = node_tree.get("rk_node_id") if node_tree else None
            node_name = (node_tree.name or "").lstrip(".") if node_tree else ""
            if node_id or (node_tree and node_name.startswith("RK_")):
                continue
            warnings.append(
                f"Material '{material.name}': Node group '{node_name}' is not RCP-aware; bake or replace."
            )
            continue

        if node_type in supported_types:
            if node_type == 'TEX_IMAGE' and getattr(node, "image", None) is None:
                warnings.append(
                    f"Material '{material.name}': Image Texture node '{node_name}' has no image."
                )
            if node_type == 'VALTORGB':
                ramp = getattr(node, "color_ramp", None)
                interpolation = (getattr(ramp, "interpolation", "LINEAR") or "LINEAR").upper()
                color_mode = (getattr(ramp, "color_mode", "RGB") or "RGB").upper()
                if color_mode != "RGB" or interpolation not in {"LINEAR", "CONSTANT", "EASE"}:
                    warnings.append(
                        f"Material '{material.name}': Color Ramp '{node_name}' {color_mode}/"
                        f"{interpolation} requires baking."
                    )
            continue

        if node_type in {'MIX_RGB', 'MIX'}:
            if _is_supported_mix(node):
                continue
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) requires baking unless "
                "it is a multiply/add/subtract or plain mix of resolvable inputs, or Factor is 0/1 "
                "with a passthrough input."
            )
            continue

        if node_type == 'MATH':
            if _is_identity_math_node(node):
                continue
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) requires baking unless "
                "it is a pass-through (add 0, subtract 0, multiply 1, divide 1)."
            )
            continue

        if node_type in partial_types:
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) has limited support; "
                "UV transforms may be ignored."
            )
            continue

        if node_type in bake_types:
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) requires baking for RCP."
            )
            continue

        if node_type in unsupported_types:
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) is not supported by RCP."
            )
            continue

        warnings.append(
            f"Material '{material.name}': Node '{node_name}' ({node_type}) is unrecognized; export may differ."
        )

    return _dedupe_warnings(warnings)


def _collect_used_nodes(material):
    """Collect nodes contributing to the active material output."""
    node_tree = material.node_tree
    used_nodes = set()
    volume_linked = False
    displacement_linked = False

    output_nodes = [n for n in node_tree.nodes if n.type == 'OUTPUT_MATERIAL']
    if not output_nodes:
        return used_nodes, volume_linked, displacement_linked

    active_output = None
    for node in output_nodes:
        if getattr(node, "is_active_output", False):
            active_output = node
            break
    if not active_output:
        active_output = output_nodes[0]

    def visit(node):
        if node in used_nodes:
            return
        used_nodes.add(node)
        for input_socket in getattr(node, "inputs", []):
            if not input_socket.is_linked:
                continue
            for link in input_socket.links:
                from_node = link.from_node
                if from_node:
                    visit(from_node)

    for socket_name in ("Surface", "Volume", "Displacement"):
        socket = active_output.inputs.get(socket_name)
        if not socket or not socket.is_linked:
            continue
        if socket_name == "Volume":
            volume_linked = True
        if socket_name == "Displacement":
            displacement_linked = True
        for link in socket.links:
            if link.from_node:
                visit(link.from_node)

    return used_nodes, volume_linked, displacement_linked


def _dedupe_warnings(warnings: List[str]) -> List[str]:
    """Deduplicate warnings while preserving order."""
    seen = set()
    deduped = []
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        deduped.append(warning)
    return deduped


def _extract_rk_group_material_data(group_node, base_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract inputs from a RealityKit node group."""
    data = dict(base_data)
    graph = _build_rk_node_graph(group_node)
    if graph:
        data['type'] = 'rk_graph'
        data['rk_graph'] = graph
        for key in (
            'base_color_texture_sources',
            'base_color_texture_alpha_modes',
            'base_color_alpha_semantics_error',
            'has_premultiplied_alpha',
        ):
            if key in graph:
                data[key] = graph[key]
        return data

    node_tree = group_node.node_tree
    node_id = node_tree.get("rk_node_id") if node_tree else None

    if not node_id:
        node_id = _infer_rk_node_id(node_tree.name if node_tree else "")

    data['type'] = 'rk_group'
    data['rk_node_id'] = node_id
    data['rk_inputs'] = _extract_group_inputs(group_node, node_id)
    base_color_inputs = [
        value
        for name, value in data['rk_inputs'].items()
        if _is_surface_base_color_input(name)
    ]
    sources = []
    for value in base_color_inputs:
        sources.extend(_texture_specs_from_value(value))
    _apply_base_color_texture_semantics(data, sources)
    if (
        data.get('has_premultiplied_alpha')
        and _input_mtlx_type(node_id, 'hasPremultipliedAlpha')
    ):
        data['rk_inputs']['hasPremultipliedAlpha'] = True
    return data


def _infer_rk_node_id(group_name: str) -> str:
    """Infer a RealityKit node id from a group name."""
    name = (group_name or "").lstrip(".").lower()
    if "pbr surface" in name or name.startswith("rk_pbr"):
        return "realitykit_pbr_surfaceshader"
    if "unlit surface" in name or name.startswith("rk_unlit"):
        return "realitykit_unlit_surfaceshader"
    return group_name


def _get_manifest() -> Dict[str, Any]:
    """Load and cache the MaterialX manifest."""
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        try:
            from ....manifest.materialx_nodes import load_manifest
            _MANIFEST_CACHE = load_manifest()
        except Exception:
            _MANIFEST_CACHE = {}
    return _MANIFEST_CACHE or {}


def _input_mtlx_type(node_id: Optional[str], input_name: str) -> Optional[str]:
    """Look up the MaterialX type for a node input."""
    if not node_id:
        return None
    manifest = _get_manifest()
    try:
        from ....manifest.materialx_nodes import select_node_def_for_node
        node_def = select_node_def_for_node(manifest, node_id)
    except Exception:
        node_def = None
    if not node_def and isinstance(node_id, str) and node_id.startswith("ND_"):
        node_def = manifest.get("nodes", {}).get(node_id)
    if not node_def:
        return None
    for input_def in node_def.get("inputs", []):
        if input_def.get("name") == input_name:
            return input_def.get("type")
    return None


def _mtlx_type_to_output_type(type_name: Optional[str]) -> Optional[str]:
    """Map MaterialX types to texture output hints."""
    if not type_name:
        return None
    type_name = type_name.lower()
    if type_name in {"color3", "half3"}:
        return "color3"
    if type_name in {"color4", "half4"}:
        return "color4"
    if type_name in {"vector2", "half2"}:
        return "vector2"
    if type_name in {"vector3"}:
        return "vector3"
    if type_name in {"vector4"}:
        return "vector4"
    if type_name in {"float", "half", "integer", "int"}:
        return "float"
    return None


def _build_rk_node_graph(surface_node) -> Optional[Dict[str, Any]]:
    """Build a MaterialX-style graph from RealityKit group nodes."""
    if not _is_rk_group_node(surface_node):
        return None

    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, str]] = []
    node_map: Dict[object, str] = {}
    used_names: Set[str] = set()

    def _unique_name(base: str) -> str:
        base = _sanitize_node_name(base)
        if base not in used_names:
            used_names.add(base)
            return base
        idx = 1
        while f"{base}_{idx}" in used_names:
            idx += 1
        name = f"{base}_{idx}"
        used_names.add(name)
        return name

    def _node_name(node) -> str:
        if node in node_map:
            return node_map[node]
        label = (node.label or node.name or node.node_tree.name or "Node")
        name = _unique_name(label)
        node_map[node] = name
        return name

    def visit(node) -> None:
        if node in node_map:
            return
        if not _is_rk_group_node(node):
            return

        node_id = node.node_tree.get("rk_node_id") if node.node_tree else None
        if not node_id:
            return

        node_name = _node_name(node)
        inputs: Dict[str, Any] = {}

        for socket in node.inputs:
            if not socket:
                continue
            input_name = socket.name

            if socket.is_linked:
                link = socket.links[0]
                from_node = link.from_node
                if _is_rk_group_node(from_node):
                    visit(from_node)
                    connections.append(
                        {
                            "from_node": _node_name(from_node),
                            "from_output": link.from_socket.name,
                            "to_node": node_name,
                            "to_input": input_name,
                        }
                    )
                    continue

                texture_path = _extract_image_path_from_socket(socket)
                if texture_path:
                    mtlx_type = _input_mtlx_type(node_id, input_name)
                    output_type = _mtlx_type_to_output_type(mtlx_type) or _socket_output_type(socket)
                    texture_spec = {
                        'type': (
                            'normal_texture'
                            if _input_expects_decoded_normal(node_id, input_name)
                            else 'texture'
                        ),
                        'path': texture_path,
                        'output_type': output_type,
                        # Without a role this texture skips the data-texture
                        # colour-space guard, so a normal or roughness image
                        # left at Blender's default sRGB is authored
                        # srgb_texture and silently decoded. The Principled
                        # path fails closed on exactly this.
                        'colorspace_role': texture_colorspace_role(input_name),
                    }
                    uv_map = _extract_uv_map_from_socket(socket)
                    if uv_map:
                        texture_spec['texcoord'] = _normalize_uv_map_name(uv_map)
                    mapping = _extract_mapping_from_socket(socket)
                    if mapping:
                        texture_spec['mapping'] = mapping
                    colorspace = _extract_colorspace_from_socket(socket)
                    if colorspace:
                        texture_spec['colorspace'] = colorspace
                    alpha_mode = _extract_alpha_mode_from_socket(socket)
                    if alpha_mode:
                        texture_spec['alpha_mode'] = alpha_mode
                    inputs[input_name] = texture_spec
                    continue

                constant = _extract_constant_from_socket(socket)
                if constant is not None:
                    inputs[input_name] = constant
                    continue

            default_value = _socket_default_value(socket)
            if default_value is not None:
                inputs[input_name] = default_value

        nodes.append(
            {
                "name": node_name,
                "node_id": node_id,
                "inputs": inputs,
            }
        )

    visit(surface_node)
    if not nodes:
        return None

    result = {
        "nodes": nodes,
        "connections": connections,
        "output": _node_name(surface_node),
    }
    _apply_base_color_texture_semantics(
        result,
        _rk_graph_base_color_texture_sources(result),
    )
    if result.get("has_premultiplied_alpha"):
        surface = next(
            (node for node in nodes if node.get("name") == result["output"]),
            None,
        )
        if surface and _input_mtlx_type(
            surface.get("node_id"),
            "hasPremultipliedAlpha",
        ):
            surface.setdefault("inputs", {})["hasPremultipliedAlpha"] = True
    return result


def _extract_group_inputs(group_node, rk_node_id: Optional[str] = None) -> Dict[str, Any]:
    """Extract group input values and texture references."""
    inputs = {}
    for socket in group_node.inputs:
        input_name = socket.name
        if socket.is_linked:
            texture_path = _extract_image_path_from_socket(socket)
            if texture_path:
                output_type = _socket_output_type(socket)
                tex_type = (
                    'normal_texture'
                    if _input_expects_decoded_normal(rk_node_id, input_name)
                    else 'texture'
                )
                texture_spec = {
                    'type': tex_type,
                    'path': texture_path,
                    'output_type': output_type,
                    # See _build_rk_node_graph: an untagged texture bypasses
                    # the data-texture colour-space guard.
                    'colorspace_role': texture_colorspace_role(input_name),
                }
                uv_map = _extract_uv_map_from_socket(socket)
                if uv_map:
                    texture_spec['texcoord'] = _normalize_uv_map_name(uv_map)
                mapping = _extract_mapping_from_socket(socket)
                if mapping:
                    texture_spec['mapping'] = mapping
                colorspace = _extract_colorspace_from_socket(socket)
                if colorspace:
                    texture_spec['colorspace'] = colorspace
                alpha_mode = _extract_alpha_mode_from_socket(socket)
                if alpha_mode:
                    texture_spec['alpha_mode'] = alpha_mode
                inputs[input_name] = texture_spec
            else:
                value = _socket_default_value(socket)
                if value is not None:
                    inputs[input_name] = value
        else:
            value = _socket_default_value(socket)
            if value is not None:
                inputs[input_name] = value

    return inputs


def _socket_output_type(socket) -> str:
    """Infer MaterialX output type for a Blender socket."""
    socket_type = getattr(socket, "type", "") or ""
    if socket_type in {'VALUE', 'FLOAT', 'INT'}:
        return 'float'
    if socket_type in {'BOOLEAN', 'BOOL'}:
        return 'boolean'
    if socket_type in {'VECTOR'}:
        return 'vector3'
    if socket_type in {'RGBA', 'COLOR'}:
        return 'color4'

    default = _socket_default_value(socket)
    if isinstance(default, (list, tuple)):
        if len(default) == 4:
            return 'color4'
        if len(default) == 3:
            return 'color3'
        if len(default) == 2:
            return 'vector2'
    return 'color3'


def _socket_default_value(socket):
    """Get a socket default value normalized to Python primitives."""
    if not hasattr(socket, "default_value"):
        return None
    value = socket.default_value
    if isinstance(value, str):
        return value
    if isinstance(value, (float, int, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        try:
            return [float(v) for v in list(value)]
        except (TypeError, ValueError):
            return None
    return None


def _is_rk_group_node(node) -> bool:
    """Return True for RealityKit-authored node groups."""
    if not node or getattr(node, "type", None) != 'GROUP':
        return False
    node_tree = getattr(node, "node_tree", None)
    if not node_tree:
        return False
    return bool(node_tree.get("rk_node_id"))


def _sanitize_node_name(value: str) -> str:
    """Sanitize a name for use as a USD prim."""
    if not value:
        return "node"
    sanitized = re.sub(r'[^A-Za-z0-9_]', '_', value)
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = f"n_{sanitized}"
    return sanitized


def _node_label(node, socket=None) -> str:
    """Return a readable node label for provenance."""
    if not node:
        return "Unknown"
    name = getattr(node, "name", None) or getattr(node, "label", None) or node.type
    socket_name = getattr(socket, "name", None)
    if socket_name:
        return f"{name} ({node.type}:{socket_name})"
    return f"{name} ({node.type})"


def _is_normal_socket(socket) -> bool:
    """Return True when a socket represents a normal input."""
    name = (socket.name or "").lower()
    return "normal" in name


def _is_unit_z_vector(value) -> bool:
    """Whether a nodedef default spells the unit Z vector, in any formatting.

    Judged numerically: the manifest carries both "0, 0, 1" (the surface
    normals) and "0.0, 0.0, 1.0" (transformnormal), and a literal string
    comparison would flip answers under any regeneration that renumbers
    defaults.
    """
    if value is None:
        return False
    parts = str(value).split(",")
    if len(parts) != 3:
        return False
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return False
    return numbers == [0.0, 0.0, 1.0]


def _input_expects_decoded_normal(node_id: Optional[str], input_name: str) -> bool:
    """Whether ``input_name`` on ``node_id`` receives a decoded normal.

    Answered from the nodedef rather than the socket name alone so both RK
    extraction paths reach the same conclusion. _extract_group_inputs decided
    this by name and got a normal_map_decode; _build_rk_node_graph never
    decided it at all and authored a raw colour->vector convert, so the same RK
    PBR Surface group produced different normals depending on which path ran.

    A vector3 input is a decoded-normal socket when its declared default is
    the unit Z vector AND its name says normal. Both conditions are load
    bearing: measured across the shipped manifest, the five real normal
    sockets (normal, clearcoatNormal, bentNormal on the RK surfaces) satisfy
    both, while ``ND_transformnormal_vector3.in`` also defaults to unit Z but
    receives an ordinary direction — the default alone is not a semantic.

    Falls back to the name when the nodedef cannot be resolved - a user node
    group with no manifest entry - which is the only signal available there.
    """
    if not input_name:
        return False
    declared_type = _input_mtlx_type(node_id, input_name)
    if declared_type == "vector3":
        default = _input_mtlx_default(node_id, input_name)
        if default is not None:
            return (
                _is_unit_z_vector(default)
                and "normal" in input_name.lower()
            )
    if declared_type is not None:
        # The nodedef resolved and this is not a decoded-normal input.
        return False
    return "normal" in input_name.lower()


def _input_mtlx_default(node_id: Optional[str], input_name: str):
    """Return the declared default for a nodedef input, or None."""
    if not node_id:
        return None
    manifest = _get_manifest()
    try:
        from ....manifest.materialx_nodes import select_node_def_for_node
        node_def = select_node_def_for_node(manifest, node_id)
    except Exception:
        node_def = None
    if not node_def and isinstance(node_id, str) and node_id.startswith("ND_"):
        node_def = manifest.get("nodes", {}).get(node_id)
    if not node_def:
        return None
    for entry in node_def.get("inputs", []) or []:
        if entry.get("name") == input_name:
            return entry.get("value")
    return None


def _extract_image_path_from_socket(socket) -> Optional[str]:
    """Get image file path from a linked socket."""
    if not socket or not socket.is_linked:
        return None

    from_node = socket.links[0].from_node
    image = _extract_image_from_node(from_node)
    return _resolve_image_path(image)


def _extract_colorspace_from_socket(socket) -> Optional[str]:
    """Get the colorspace name from a linked image texture."""
    image_node = _extract_image_node_from_socket(socket)
    if not image_node or not getattr(image_node, "image", None):
        return None
    try:
        name = image_node.image.colorspace_settings.name
    except Exception:
        return None
    return _normalize_colorspace(name)


def _extract_alpha_mode_from_socket(socket) -> Optional[str]:
    """Get alpha mode for a linked image texture."""
    image_node = _extract_image_node_from_socket(socket)
    if not image_node or not getattr(image_node, "image", None):
        return None
    mode = getattr(image_node.image, "alpha_mode", None)
    if not mode:
        return None
    mode = str(mode).upper()
    if mode == 'PREMUL':
        return 'premul'
    if mode == 'STRAIGHT':
        return 'straight'
    return mode.lower()


def _extract_image_node_from_socket(socket):
    """Resolve the image node linked into a socket, if any."""
    if not socket or not socket.is_linked:
        return None
    from_node = socket.links[0].from_node
    return _extract_image_node(from_node)


def _extract_mapping_from_socket(socket) -> Optional[Dict[str, Any]]:
    """Get UV mapping transform info from a linked socket."""
    image_node = _extract_image_node_from_socket(socket)
    if not image_node:
        return None
    vector_socket = image_node.inputs.get("Vector") if hasattr(image_node, "inputs") else None
    if not vector_socket or not vector_socket.is_linked:
        return None
    return _extract_mapping_from_node(vector_socket.links[0].from_node)

def _extract_uv_map_from_socket(socket) -> Optional[str]:
    """Get UV map name for a linked texture socket if present."""
    if not socket or not socket.is_linked:
        return None

    from_node = socket.links[0].from_node
    image_node = _extract_image_node(from_node)
    if not image_node:
        return None

    uv_map = getattr(image_node, "uv_map", "") or ""
    if uv_map:
        return uv_map

    vector_socket = image_node.inputs.get("Vector") if hasattr(image_node, "inputs") else None
    if vector_socket and vector_socket.is_linked:
        return _extract_uv_map_from_node(vector_socket.links[0].from_node)
    return None


def _get_surface_shader_node(material):
    """Return the shader node connected to the active Material Output surface."""
    node_tree = material.node_tree
    output_nodes = [n for n in node_tree.nodes if n.type == 'OUTPUT_MATERIAL']
    if not output_nodes:
        return None

    active_output = None
    for node in output_nodes:
        if getattr(node, "is_active_output", False):
            active_output = node
            break
    if not active_output:
        active_output = output_nodes[0]

    surface_socket = active_output.inputs.get('Surface')
    if not surface_socket or not surface_socket.is_linked:
        return None
    link = surface_socket.links[0]
    return link.from_node if link else None


def _extract_image_from_node(node):
    """Resolve an image from known Blender node types."""
    image_node = _extract_image_node(node)
    if image_node:
        return image_node.image
    return None


def _extract_image_node(node):
    """Resolve an image node from known Blender node types."""
    if not node:
        return None

    if node.type == 'TEX_IMAGE':
        return node

    if node.type in {'SEPARATE_COLOR', 'SEPARATE_RGB'}:
        input_socket = node.inputs.get('Color') if hasattr(node, "inputs") else None
        if input_socket is None:
            input_socket = node.inputs.get('Image') if hasattr(node, "inputs") else None
        if input_socket and input_socket.is_linked:
            return _extract_image_node(input_socket.links[0].from_node)

    if node.type == 'NORMAL_MAP':
        color_socket = node.inputs.get('Color')
        if color_socket and color_socket.is_linked:
            return _extract_image_node(color_socket.links[0].from_node)

    if node.type == 'BUMP':
        height_socket = node.inputs.get('Height')
        if height_socket and height_socket.is_linked:
            return _extract_image_node(height_socket.links[0].from_node)

    return None


def _resolve_socket_value(
    socket,
    visited=None,
    channel=None,
    provenance=None,
    cache: Optional[Dict[Any, Dict[str, Any]]] = None,
    expected_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a linked socket to a texture or constant spec."""
    if not socket or not socket.is_linked:
        return None

    if visited is None:
        visited = set()
    if provenance is None:
        provenance = []

    cache_key = None
    if cache is not None and hasattr(socket, "as_pointer"):
        try:
            cache_key = (socket.as_pointer(), channel, expected_type)
        except Exception:
            cache_key = None
    if cache is not None and cache_key is not None and cache_key in cache:
        return dict(cache[cache_key])

    link = socket.links[0]
    from_node = getattr(link, "from_node", None)
    from_socket = getattr(link, "from_socket", None)
    if not from_node:
        return None

    if from_node in visited:
        return None
    visited.add(from_node)

    provenance.append(_node_label(from_node, from_socket))
    node_type = getattr(from_node, "type", "")

    if node_type == 'REROUTE':
        input_socket = from_node.inputs[0] if from_node.inputs else None
        return _resolve_socket_value(
            input_socket,
            visited,
            channel,
            provenance,
            cache,
            expected_type=expected_type,
        )

    if node_type in {'SEPARATE_COLOR', 'SEPARATE_RGB'}:
        ch = channel or _channel_from_socket_name(from_socket.name if from_socket else "")
        input_socket = from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None
        if input_socket is None and hasattr(from_node, "inputs") and from_node.inputs:
            input_socket = from_node.inputs[0]
        resolved = _resolve_socket_value(
            input_socket,
            visited,
            ch,
            provenance,
            cache,
            expected_type='float',
        )
        if resolved and ch:
            resolved.setdefault("channel", ch)
        return resolved

    if node_type in {'SEPARATE_XYZ', 'SEPXYZ'}:
        ch = channel or _channel_from_socket_name(from_socket.name if from_socket else "")
        input_socket = from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None
        if input_socket is None and hasattr(from_node, "inputs") and from_node.inputs:
            input_socket = from_node.inputs[0]
        resolved = _resolve_socket_value(
            input_socket,
            visited,
            ch,
            provenance,
            cache,
            expected_type='float',
        )
        if resolved and ch:
            resolved.setdefault("channel", ch)
        return resolved

    if node_type == 'NORMAL_MAP':
        color_socket = from_node.inputs.get('Color')
        resolved = _resolve_socket_value(
            color_socket,
            visited,
            channel,
            provenance,
            cache,
            expected_type=expected_type,
        )
        if resolved and resolved.get("kind") == "texture":
            # Preserve Normal Map node parameters (best-effort; linked strength is not handled).
            strength_socket = from_node.inputs.get('Strength') if hasattr(from_node, "inputs") else None
            if strength_socket and not getattr(strength_socket, "is_linked", False):
                try:
                    resolved["scale"] = float(strength_socket.default_value)
                except Exception:
                    pass

            space = getattr(from_node, "space", None)
            if space:
                space = str(space).upper()
                if "TANGENT" in space:
                    resolved["space"] = "tangent"
                elif "OBJECT" in space:
                    resolved["space"] = "object"
        return resolved

    if node_type == 'BUMP':
        height_socket = from_node.inputs.get('Height')
        return _resolve_socket_value(
            height_socket,
            visited,
            channel,
            provenance,
            cache,
            expected_type=expected_type,
        )

    if node_type == 'MAPPING':
        vector_socket = from_node.inputs.get('Vector')
        return _resolve_socket_value(
            vector_socket,
            visited,
            channel,
            provenance,
            cache,
            expected_type=expected_type,
        )

    if node_type == 'GROUP':
        group_tree = getattr(from_node, "node_tree", None)
        if not group_tree:
            return {"kind": "unresolved", "provenance": list(provenance)}

        outputs = [n for n in group_tree.nodes if n.type == 'GROUP_OUTPUT']
        if not outputs:
            return {"kind": "unresolved", "provenance": list(provenance)}
        output_node = next((n for n in outputs if getattr(n, "is_active_output", False)), outputs[0])

        input_socket = None
        if from_socket and hasattr(output_node, "inputs"):
            input_socket = output_node.inputs.get(from_socket.name)
        if input_socket is None and from_socket and hasattr(from_node, "outputs"):
            try:
                index = list(from_node.outputs).index(from_socket)
                if hasattr(output_node, "inputs") and index < len(output_node.inputs):
                    input_socket = output_node.inputs[index]
            except Exception:
                input_socket = None

        if input_socket and input_socket.is_linked:
            return _resolve_socket_value(
                input_socket,
                visited,
                channel,
                provenance,
                cache,
                expected_type=expected_type,
            )
        return {"kind": "unresolved", "provenance": list(provenance)}

    if node_type in {'MIX_RGB', 'MIX'}:
        blend, fac, a_socket, b_socket = _mix_node_params(from_node)
        if fac is not None:
            # Blender Mix is out = lerp(A, op(A, B), fac), so Factor 0 is input A
            # for *every* blend mode (the blended term drops out entirely).
            if fac == 0.0 and a_socket and a_socket.is_linked:
                return _resolve_socket_value(
                    a_socket, visited, channel, provenance, cache,
                    expected_type=expected_type,
                )
            if blend == 'MIX':
                # Plain mix: out = lerp(A, B, fac). Factor 1 is input B.
                if fac == 1.0 and b_socket and b_socket.is_linked:
                    return _resolve_socket_value(
                        b_socket, visited, channel, provenance, cache,
                        expected_type=expected_type,
                    )
                if a_socket and b_socket and a_socket.is_linked and b_socket.is_linked:
                    a_expr = _expr_from_socket(a_socket, visited, channel, provenance, cache)
                    b_expr = _expr_from_socket(b_socket, visited, channel, provenance, cache)
                    if a_expr is not None and b_expr is not None:
                        return _make_node_expr(
                            _nodedef_for("mix", expected_type or "color3"),
                            {"bg": a_expr, "fg": b_expr, "mix": _constant_expr(fac)},
                        )
            else:
                # Combining blends: out = lerp(A, op(A, B), fac). Emit op(A, B)
                # so e.g. a diffuse x AO multiply survives as a real MaterialX
                # node instead of collapsing to one of its inputs.
                op_name = {
                    'MULTIPLY': 'multiply',
                    'ADD': 'add',
                    'SUBTRACT': 'subtract',
                }.get(blend)
                if (
                    op_name is not None
                    and a_socket and b_socket
                    and a_socket.is_linked and b_socket.is_linked
                ):
                    a_expr = _expr_from_socket(a_socket, visited, channel, provenance, cache)
                    b_expr = _expr_from_socket(b_socket, visited, channel, provenance, cache)
                    if a_expr is not None and b_expr is not None:
                        blended = _make_node_expr(
                            _nodedef_for(op_name, expected_type or "color3"),
                            {"in1": a_expr, "in2": b_expr},
                        )
                        if fac == 1.0:
                            return blended
                        return _make_node_expr(
                            _nodedef_for("mix", expected_type or "color3"),
                            {"bg": a_expr, "fg": blended, "mix": _constant_expr(fac)},
                        )

    if node_type == 'MATH':
        operation = (getattr(from_node, "operation", "") or "").upper()
        if hasattr(from_node, "inputs") and len(from_node.inputs) >= 2:
            in0 = from_node.inputs[0]
            in1 = from_node.inputs[1]
            if in0 and in0.is_linked and (not in1 or not in1.is_linked):
                try:
                    value = float(in1.default_value)
                except Exception:
                    value = None
                if _is_identity_math(operation, value, linked_index=0):
                    return _resolve_socket_value(
                        in0,
                        visited,
                        channel,
                        provenance,
                        cache,
                        expected_type=expected_type,
                    )
            if in1 and in1.is_linked and (not in0 or not in0.is_linked):
                try:
                    value = float(in0.default_value)
                except Exception:
                    value = None
                if _is_identity_math(operation, value, linked_index=1):
                    return _resolve_socket_value(
                        in1,
                        visited,
                        channel,
                        provenance,
                        cache,
                        expected_type=expected_type,
                    )

    if node_type == 'CLAMP':
        value_expr = _expr_from_socket(
            from_node.inputs.get('Value') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if value_expr is None and hasattr(from_node, "inputs") and from_node.inputs:
            value_expr = _expr_from_socket(
                from_node.inputs[0],
                visited,
                channel,
                provenance,
                cache,
            )
        low_expr = _expr_from_socket(
            from_node.inputs.get('Min') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        high_expr = _expr_from_socket(
            from_node.inputs.get('Max') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        node_id = _nodedef_for("clamp", expected_type or "float")
        return _make_node_expr(
            node_id,
            {"in": value_expr, "low": low_expr, "high": high_expr},
        )

    if node_type == 'MAP_RANGE':
        value_expr = _expr_from_socket(
            from_node.inputs.get('Value') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        in_min = _expr_from_socket(
            from_node.inputs.get('From Min') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        in_max = _expr_from_socket(
            from_node.inputs.get('From Max') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        out_min = _expr_from_socket(
            from_node.inputs.get('To Min') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        out_max = _expr_from_socket(
            from_node.inputs.get('To Max') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        inputs = {
            "in": value_expr,
            "inlow": in_min,
            "inhigh": in_max,
            "outlow": out_min,
            "outhigh": out_max,
            "gamma": _constant_expr(1.0),
        }
        if getattr(from_node, "clamp", False):
            inputs["doclamp"] = _constant_expr(True)
        node_id = _nodedef_for("range", expected_type or "float")
        return _make_node_expr(node_id, inputs)

    if node_type == 'HUE_SAT':
        color_expr = _expr_from_socket(
            from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        hue_expr = _expr_from_socket(
            from_node.inputs.get('Hue') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.5,
        )
        sat_expr = _expr_from_socket(
            from_node.inputs.get('Saturation') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        val_expr = _expr_from_socket(
            from_node.inputs.get('Value') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        amount_expr = _make_node_expr(
            _nodedef_for("combine3", "vector3"),
            {"in1": hue_expr, "in2": sat_expr, "in3": val_expr},
        )
        hsv_expr = _make_node_expr(
            # hsvadjust only outputs colours; an expected float used to leak a
            # bare node name into the stage. Request the natural type and let
            # the authoring-time conversion produce the float.
            _nodedef_for("hsvadjust", "color3"),
            {"in": color_expr, "amount": amount_expr},
        )
        fac_expr = _expr_from_socket(
            from_node.inputs.get('Fac') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        if _expr_is_constant(fac_expr, 1.0):
            return hsv_expr
        mix_inputs = {
            "fg": hsv_expr,
            "bg": color_expr,
            "mix": fac_expr,
        }
        return _make_node_expr(_nodedef_for("mix", expected_type or "color3"), mix_inputs)

    if node_type == 'INVERT':
        color_expr = _expr_from_socket(
            from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if color_expr is None:
            return {"kind": "unresolved", "provenance": list(provenance)}
        if expected_type and expected_type.startswith("vector"):
            return color_expr

        wants_float = expected_type in {'float', 'half', 'integer'}
        if wants_float:
            is_float_like = False
            if isinstance(color_expr, dict):
                if color_expr.get("kind") == "constant":
                    is_float_like = not isinstance(color_expr.get("value"), (list, tuple))
                elif color_expr.get("kind") == "texture":
                    out_type = (color_expr.get("output_type") or "").lower()
                    is_float_like = out_type == "float" or bool(color_expr.get("channel"))

            if is_float_like:
                return _make_node_expr(
                    _nodedef_for("oneminus", "float"),
                    {"in": color_expr},
                )

            invert_color = _make_node_expr(
                _nodedef_for("oneminus", "color3"),
                {"in": color_expr},
            )
            swizzle_signature = "in[in:color3,channels:string]|out[out:float]"
            swizzle_node = select_nodedef_name_for_node(
                _get_manifest(),
                "swizzle",
                signature=swizzle_signature,
                output_type="float",
            ) or "ND_swizzle_color3_float"
            return _make_node_expr(
                swizzle_node,
                {"in": invert_color, "channels": _constant_expr(channel or "r")},
            )
        fac_expr = _expr_from_socket(
            from_node.inputs.get('Fac') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        if _expr_is_constant(fac_expr, 0.0):
            return color_expr
        invert_expr = _make_node_expr(
            _nodedef_for("oneminus", expected_type or "color3"),
            {"in": color_expr},
        )
        if _expr_is_constant(fac_expr, 1.0):
            return invert_expr
        return _make_node_expr(
            _nodedef_for("mix", expected_type or "color3"),
            {"fg": invert_expr, "bg": color_expr, "mix": fac_expr},
        )

    if node_type == 'BRIGHTCONTRAST':
        color_expr = _expr_from_socket(
            from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        bright_expr = _expr_from_socket(
            from_node.inputs.get('Bright') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        contrast_expr = _expr_from_socket(
            from_node.inputs.get('Contrast') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        contrast_amount = _make_node_expr(
            _nodedef_for("add", "float"),
            {"in1": contrast_expr, "in2": _constant_expr(1.0)},
        )
        contrast_node = _make_node_expr(
            _nodedef_for("contrast", expected_type or "color3"),
            {"in": color_expr, "amount": contrast_amount, "pivot": _constant_expr(0.5)},
        )
        if _expr_is_constant(bright_expr, 0.0):
            return contrast_node
        bright_color = _make_node_expr(
            _nodedef_for("combine3", "color3"),
            {"in1": bright_expr, "in2": bright_expr, "in3": bright_expr},
        )
        return _make_node_expr(
            _nodedef_for("add", expected_type or "color3"),
            {"in1": contrast_node, "in2": bright_color},
        )

    if node_type == 'VALTORGB':
        fac_expr = _expr_from_socket(
            from_node.inputs.get('Fac') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        ramp = getattr(from_node, "color_ramp", None)
        elements = sorted(
            list(getattr(ramp, "elements", []) or []),
            key=lambda item: float(getattr(item, "position", 0.0)),
        )
        if len(elements) < 2:
            return {"kind": "unresolved", "provenance": list(provenance)}

        interpolation = (getattr(ramp, "interpolation", "LINEAR") or "LINEAR").upper()
        color_mode = (getattr(ramp, "color_mode", "RGB") or "RGB").upper()
        if color_mode != "RGB" or interpolation not in {"LINEAR", "CONSTANT", "EASE"}:
            return {
                "kind": "unresolved",
                "provenance": list(provenance),
                "reason": (
                    f"Color Ramp mode {color_mode}/{interpolation} requires baking; "
                    "the OS 27 exporter supports RGB Linear, Constant, and Ease"
                ),
            }

        output_name = (getattr(from_socket, "name", "") or "").lower()
        alpha_output = output_name == "alpha"
        ramp_type = "float" if alpha_output else "color3"

        stops = []
        for element in elements:
            position = float(getattr(element, "position", 0.0))
            color = list(getattr(element, "color", (0.0, 0.0, 0.0, 1.0)))
            while len(color) < 4:
                color.append(1.0)
            value = float(color[3]) if alpha_output else [float(v) for v in color[:3]]
            stops.append((position, value))

        result = _constant_expr(stops[0][1])
        for index in range(1, len(stops)):
            left_position, left_value = stops[index - 1]
            right_position, right_value = stops[index]

            if interpolation == "CONSTANT" or right_position <= left_position:
                result = _make_node_expr(
                    _nodedef_for("ifgreatereq", ramp_type),
                    {
                        "value1": fac_expr,
                        "value2": _constant_expr(right_position),
                        "in1": _constant_expr(right_value),
                        "in2": result,
                    },
                )
                continue

            if interpolation == "EASE":
                mix_factor = _make_node_expr(
                    _nodedef_for("smoothstep", "float"),
                    {
                        "in": fac_expr,
                        "low": _constant_expr(left_position),
                        "high": _constant_expr(right_position),
                    },
                )
            else:
                mix_factor = _make_node_expr(
                    _nodedef_for("range", "float"),
                    {
                        "in": fac_expr,
                        "inlow": _constant_expr(left_position),
                        "inhigh": _constant_expr(right_position),
                        "outlow": _constant_expr(0.0),
                        "outhigh": _constant_expr(1.0),
                        "gamma": _constant_expr(1.0),
                        "doclamp": _constant_expr(True),
                    },
                )
            segment = _make_node_expr(
                _nodedef_for("mix", ramp_type),
                {
                    "bg": _constant_expr(left_value),
                    "fg": _constant_expr(right_value),
                    "mix": mix_factor,
                },
            )
            result = _make_node_expr(
                _nodedef_for("ifgreatereq", ramp_type),
                {
                    "value1": fac_expr,
                    "value2": _constant_expr(left_position),
                    "in1": segment,
                    "in2": result,
                },
            )
        return result

    if node_type == 'CURVE_RGB':
        color_expr = _expr_from_socket(
            from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if color_expr is None:
            return {"kind": "unresolved", "provenance": list(provenance)}

        if expected_type and expected_type not in {'color3', 'color4'}:
            # Curve RGB is a color operation; pass through for non-color targets (e.g. normals).
            return color_expr

        fac_expr = _expr_from_socket(
            from_node.inputs.get('Fac') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )

        mapping = getattr(from_node, "mapping", None)
        curves = list(getattr(mapping, "curves", []) or []) if mapping else []
        if not curves:
            return {"kind": "unresolved", "provenance": list(provenance)}

        # Blender 5.2 stores RGB curves as R, G, B, Combined.
        red_curve = curves[0] if len(curves) > 0 else None
        green_curve = curves[1] if len(curves) > 1 else red_curve
        blue_curve = curves[2] if len(curves) > 2 else red_curve
        combined_curve = curves[3] if len(curves) > 3 else None

        combined_knots = _curve_knots_from_curve(combined_curve)
        red_knots = _curve_knots_from_curve(red_curve)
        green_knots = _curve_knots_from_curve(green_curve)
        blue_knots = _curve_knots_from_curve(blue_curve)

        combined_identity = _curve_is_identity(combined_knots)
        red_identity = _curve_is_identity(red_knots)
        green_identity = _curve_is_identity(green_knots)
        blue_identity = _curve_is_identity(blue_knots)

        if combined_identity and red_identity and green_identity and blue_identity:
            if _expr_is_constant(fac_expr, 1.0):
                return color_expr
            if _expr_is_constant(fac_expr, 0.0):
                return color_expr

        # separate3's outputs are floats; the variant is picked by what it
        # accepts. Requesting output color3 was unsatisfiable and leaked a
        # bare 'separate3' id (latent: this block is bake-gated today).
        separate_id = _nodedef_for("separate3", "float", input_type="color3")

        def channel_expr(output_name: str) -> Dict[str, Any]:
            return _make_node_expr(separate_id, {"in": color_expr}, output=output_name)

        def apply_curve(expr: Dict[str, Any], knots: List[List[float]]) -> Dict[str, Any]:
            if not knots:
                return expr
            return _make_node_expr(
                _nodedef_for("curveadjust", "float"),
                {"in": expr, "knots": _constant_expr(knots)},
            )

        r_expr = channel_expr("outr")
        g_expr = channel_expr("outg")
        b_expr = channel_expr("outb")

        if not combined_identity:
            r_expr = apply_curve(r_expr, combined_knots)
            g_expr = apply_curve(g_expr, combined_knots)
            b_expr = apply_curve(b_expr, combined_knots)

        if not red_identity:
            r_expr = apply_curve(r_expr, red_knots)
        if not green_identity:
            g_expr = apply_curve(g_expr, green_knots)
        if not blue_identity:
            b_expr = apply_curve(b_expr, blue_knots)

        combined_expr = _make_node_expr(
            _nodedef_for("combine3", "color3"),
            {"in1": r_expr, "in2": g_expr, "in3": b_expr},
        )

        if _expr_is_constant(fac_expr, 1.0):
            return combined_expr
        if _expr_is_constant(fac_expr, 0.0):
            return color_expr

        return _make_node_expr(
            _nodedef_for("mix", "color3"),
            {"fg": combined_expr, "bg": color_expr, "mix": fac_expr},
        )

    if node_type == 'RGBTOBW':
        color_expr = _expr_from_socket(
            from_node.inputs.get('Color') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        # luminance only outputs color3; requesting float returned a bare node
        # name that shipped as a fabricated info:id. The downstream conversion
        # (luminance -> swizzle r) turns the grayscale into a float exactly.
        return _make_node_expr(_nodedef_for("luminance", "color3"), {"in": color_expr})

    if node_type == 'COMBINE_COLOR':
        mode = (getattr(from_node, "mode", "") or "").upper()
        if mode and mode != "RGB":
            return {"kind": "unresolved", "provenance": list(provenance)}
        r_expr = _expr_from_socket(
            from_node.inputs.get('R') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        g_expr = _expr_from_socket(
            from_node.inputs.get('G') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        b_expr = _expr_from_socket(
            from_node.inputs.get('B') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        a_socket = from_node.inputs.get('A') if hasattr(from_node, "inputs") else None
        if a_socket:
            a_expr = _expr_from_socket(
                a_socket,
                visited,
                channel,
                provenance,
                cache,
                default=1.0,
            )
            return _make_node_expr(
                _nodedef_for("combine4", "color4"),
                {"in1": r_expr, "in2": g_expr, "in3": b_expr, "in4": a_expr},
            )
        return _make_node_expr(
            _nodedef_for("combine3", "color3"),
            {"in1": r_expr, "in2": g_expr, "in3": b_expr},
        )

    if node_type == 'VECTOR_ROTATE':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        axis_expr = _expr_from_socket(
            from_node.inputs.get('Axis') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=(0.0, 0.0, 1.0),
        )
        angle_expr = _expr_from_socket(
            from_node.inputs.get('Angle') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        return _make_node_expr(
            _nodedef_for("rotate3d", "vector3"),
            {"in": vector_expr, "axis": axis_expr, "amount": angle_expr},
        )

    if node_type == 'VECTOR_TRANSFORM':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        vector_type = (getattr(from_node, "vector_type", "") or "").upper()
        if vector_type == 'NORMAL':
            node_id = _nodedef_for("transformnormal", "vector3")
        elif vector_type == 'POINT':
            node_id = _nodedef_for("transformpoint", "vector3")
        else:
            node_id = _nodedef_for("transformvector", "vector3")
        return _make_node_expr(node_id, {"in": vector_expr})

    if node_type == 'NORMAL':
        output = from_node.outputs.get('Normal') if hasattr(from_node, "outputs") else None
        value = None
        if output:
            try:
                value = list(output.default_value)[:3]
            except Exception:
                value = None
        if value is not None:
            return {"kind": "constant", "value": value}
        return _make_node_expr(_nodedef_for("normal", "vector3"), {"space": "world"})

    if node_type == 'TEX_NOISE':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if vector_expr is None:
            vector_expr = _default_texcoord_expr(vector_dim=3)
        scale_expr = _expr_from_socket(
            from_node.inputs.get('Scale') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        detail_expr = _expr_from_socket(
            from_node.inputs.get('Detail') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=2.0,
        )
        rough_expr = _expr_from_socket(
            from_node.inputs.get('Roughness') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.5,
        )
        distort_expr = _expr_from_socket(
            from_node.inputs.get('Distortion') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.0,
        )
        node_id = _nodedef_for("unifiednoise3d", "float")
        inputs = {
            "position": vector_expr,
            "freq": _make_node_expr(
                _nodedef_for("combine3", "vector3"),
                {"in1": scale_expr, "in2": scale_expr, "in3": scale_expr},
            ),
            "offset": _constant_expr((0.0, 0.0, 0.0)),
            "jitter": distort_expr,
            "octaves": detail_expr,
            "lacunarity": _constant_expr(2.0),
            "diminish": rough_expr,
            "type": _constant_expr(0),
        }
        return _make_node_expr(node_id, inputs)

    if node_type == 'TEX_VORONOI':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if vector_expr is None:
            vector_expr = _default_texcoord_expr(vector_dim=3)
        jitter_expr = _expr_from_socket(
            from_node.inputs.get('Randomness') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=1.0,
        )
        node_id = _nodedef_for("worleynoise3d", "float")
        return _make_node_expr(node_id, {"position": vector_expr, "jitter": jitter_expr})

    if node_type == 'TEX_GRADIENT':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        texcoord_expr = vector_expr or _default_texcoord_expr(vector_dim=2)
        return _make_node_expr(
            _nodedef_for("ramplr", "float"),
            {"valuel": _constant_expr(0.0), "valuer": _constant_expr(1.0), "texcoord": texcoord_expr},
        )

    if node_type == 'TEX_ENVIRONMENT':
        texture_info = _texture_info_from_image_node(from_node)
        if texture_info:
            if expected_type:
                texture_info.setdefault("output_type", expected_type)
            if cache is not None and cache_key is not None:
                cache[cache_key] = dict(texture_info)
            return texture_info

    if node_type == 'TEX_IMAGE':
        texture_info = _texture_info_from_image_node(from_node)
        if not texture_info:
            return None
        image_channel = _image_channel_from_output_socket(from_socket)
        if image_channel:
            texture_info["channel"] = image_channel
            if image_channel == "a":
                texture_info["output_type"] = "float"
        if expected_type:
            texture_info.setdefault("output_type", expected_type)
        if channel:
            texture_info.setdefault("channel", channel)
        if cache is not None and cache_key is not None:
            cache[cache_key] = dict(texture_info)
        return texture_info

    if node_type in {'INPUT_BOOL', 'INPUT_INT', 'INPUT_VECTOR'}:
        value = _input_constant_node_value(from_node)
        if value is None:
            return None
        result = {"kind": "constant", "value": value}
        if cache is not None and cache_key is not None:
            cache[cache_key] = dict(result)
        return result

    if node_type == 'RGB':
        output = from_node.outputs.get('Color') if hasattr(from_node, "outputs") else None
        value = None
        if output:
            try:
                value = list(output.default_value)[:3]
            except Exception:
                value = None
        if value is None:
            try:
                value = list(from_node.outputs[0].default_value)[:3]
            except Exception:
                value = None
        if value is None:
            return None
        result = {"kind": "constant", "value": value}
        if cache is not None and cache_key is not None:
            cache[cache_key] = dict(result)
        return result

    if node_type == 'VALUE':
        output = from_node.outputs.get('Value') if hasattr(from_node, "outputs") else None
        value = None
        if output:
            try:
                value = float(output.default_value)
            except Exception:
                value = None
        if value is None and hasattr(from_node, "outputs") and from_node.outputs:
            try:
                value = float(from_node.outputs[0].default_value)
            except Exception:
                value = None
        if value is None:
            return None
        result = {"kind": "constant", "value": value}
        if cache is not None and cache_key is not None:
            cache[cache_key] = dict(result)
        return result

    # Unsupported node type: return unresolved with provenance chain.
    if cache is not None and cache_key is not None:
        cache[cache_key] = {"kind": "unresolved", "provenance": list(provenance)}
    return {"kind": "unresolved", "provenance": list(provenance)}

    return None


def _texture_info_from_image_node(image_node) -> Optional[Dict[str, Any]]:
    """Build a texture spec from a Blender image node."""
    image = getattr(image_node, "image", None)
    texture_path = _resolve_image_path(image)
    if not texture_path:
        return None

    uv_map = getattr(image_node, "uv_map", "") or ""
    vector_socket = image_node.inputs.get("Vector") if hasattr(image_node, "inputs") else None
    if not uv_map and vector_socket and vector_socket.is_linked:
        uv_map = _extract_uv_map_from_node(vector_socket.links[0].from_node)

    mapping = None
    if vector_socket and vector_socket.is_linked:
        mapping = _extract_mapping_from_node(vector_socket.links[0].from_node)

    colorspace = None
    try:
        colorspace = _normalize_colorspace(image.colorspace_settings.name) if image else None
    except Exception:
        colorspace = None

    alpha_mode = None
    try:
        mode = getattr(image, "alpha_mode", None)
        if mode:
            mode = str(mode).upper()
            if mode == 'PREMUL':
                alpha_mode = 'premul'
            elif mode == 'STRAIGHT':
                alpha_mode = 'straight'
            else:
                alpha_mode = mode.lower()
    except Exception:
        alpha_mode = None

    return {
        "kind": "texture",
        "path": texture_path,
        "uv_map": uv_map or None,
        "mapping": mapping,
        "colorspace": colorspace,
        "alpha_mode": alpha_mode,
        "current_pixel_snapshot": bool(
            getattr(image, "is_dirty", False)
            or (getattr(image, "source", "") or "").upper() == "GENERATED"
        ),
    }


def _expression_has_current_pixel_snapshot(expr: Any) -> bool:
    if not isinstance(expr, dict):
        return False
    if expr.get("current_pixel_snapshot"):
        return True
    return any(
        _expression_has_current_pixel_snapshot(child)
        for child in (expr.get("inputs") or {}).values()
    )


def _expression_texture_sources(expr: Any) -> List[Dict[str, Any]]:
    """Return every texture leaf in a supported MaterialX expression."""
    if not isinstance(expr, dict):
        return []
    sources: List[Dict[str, Any]] = []
    if expr.get("kind") == "texture" and expr.get("path"):
        sources.append(
            {
                "path": str(expr["path"]),
                "alpha_mode": expr.get("alpha_mode"),
            }
        )
    for child in (expr.get("inputs") or {}).values():
        sources.extend(_expression_texture_sources(child))
    return sources


def _texture_specs_from_value(value: Any) -> List[Dict[str, Any]]:
    """Return texture specs from either expression or RK graph payloads."""
    if not isinstance(value, dict):
        return []
    sources: List[Dict[str, Any]] = []
    is_texture = value.get("kind") == "texture" or value.get("type") in {
        "texture",
        "normal_texture",
    }
    if is_texture and value.get("path"):
        sources.append(
            {
                "path": str(value["path"]),
                "alpha_mode": value.get("alpha_mode"),
                "output_type": value.get("output_type"),
            }
        )
    for child in (value.get("inputs") or {}).values():
        sources.extend(_texture_specs_from_value(child))
    return sources


def _is_surface_base_color_input(input_name: str) -> bool:
    normalized = str(input_name or "").replace("_", "").replace(" ", "").lower()
    return normalized in {"basecolor", "color"}


def _rk_graph_base_color_texture_sources(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collect color texture leaves feeding an RK surface's base-color input."""
    nodes_by_name = {
        node.get("name"): node
        for node in graph.get("nodes", [])
        if node.get("name")
    }
    output_name = graph.get("output")
    surface = nodes_by_name.get(output_name)
    if surface is None:
        return []

    sources: List[Dict[str, Any]] = []
    for input_name, value in (surface.get("inputs") or {}).items():
        if _is_surface_base_color_input(input_name):
            sources.extend(_texture_specs_from_value(value))

    incoming = {}
    for connection in graph.get("connections", []):
        incoming.setdefault(connection.get("to_node"), []).append(connection)
    stack = [
        connection.get("from_node")
        for connection in incoming.get(output_name, [])
        if _is_surface_base_color_input(connection.get("to_input"))
    ]
    visited = set()
    while stack:
        node_name = stack.pop()
        if not node_name or node_name in visited:
            continue
        visited.add(node_name)
        node = nodes_by_name.get(node_name)
        if node is None:
            continue
        for value in (node.get("inputs") or {}).values():
            for source in _texture_specs_from_value(value):
                if str(source.get("output_type") or "").lower() in {
                    "color3",
                    "color4",
                }:
                    sources.append(source)
        stack.extend(
            connection.get("from_node")
            for connection in incoming.get(node_name, [])
        )
    return sources


def _apply_base_color_texture_semantics(
    data: Dict[str, Any],
    sources: List[Dict[str, Any]],
) -> None:
    """Attach surface-wide alpha semantics derived only from base color."""
    unique_sources = []
    seen = set()
    for source in sources:
        path = str(source.get("path") or "")
        if not path:
            continue
        alpha_mode = str(source.get("alpha_mode") or "").strip().lower() or None
        key = (path, alpha_mode)
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append({"path": path, "alpha_mode": alpha_mode})
    if not unique_sources:
        return

    data["base_color_texture_sources"] = unique_sources
    modes = sorted(
        {
            source["alpha_mode"]
            for source in unique_sources
            if source.get("alpha_mode")
        }
    )
    if modes:
        data["base_color_texture_alpha_modes"] = modes
    if modes == ["premul"]:
        data["has_premultiplied_alpha"] = True
    else:
        data.pop("has_premultiplied_alpha", None)
    if "premul" in modes and any(mode != "premul" for mode in modes):
        data["base_color_alpha_semantics_error"] = (
            "Base Color combines textures with incompatible alpha conventions: "
            + ", ".join(modes)
        )


def _record_base_color_texture_semantics(data: Dict[str, Any], expr: Any) -> None:
    _apply_base_color_texture_semantics(data, _expression_texture_sources(expr))


def _extract_channel_from_socket(socket) -> Optional[str]:
    """Get a channel swizzle hint from a linked Separate node."""
    if not socket or not socket.is_linked:
        return None
    link = socket.links[0]
    from_node = getattr(link, "from_node", None)
    from_socket = getattr(link, "from_socket", None)
    if not from_node or not from_socket:
        return None

    if from_node.type in {'SEPARATE_COLOR', 'SEPARATE_RGB'}:
        name = (from_socket.name or "").lower()
        if name in {"r", "red"}:
            return "r"
        if name in {"g", "green"}:
            return "g"
        if name in {"b", "blue"}:
            return "b"
        if name in {"a", "alpha"}:
            return "a"
        return None

    if from_node.type in {'SEPARATE_XYZ', 'SEPXYZ'}:
        name = (from_socket.name or "").lower()
        if name in {"x"}:
            return "x"
        if name in {"y"}:
            return "y"
        if name in {"z"}:
            return "z"

    return None


def _channel_from_socket_name(name: str) -> Optional[str]:
    """Normalize a socket name to a channel token."""
    name = (name or "").lower()
    if name in {"r", "red"}:
        return "r"
    if name in {"g", "green"}:
        return "g"
    if name in {"b", "blue"}:
        return "b"
    if name in {"a", "alpha"}:
        return "a"
    if name == "x":
        return "x"
    if name == "y":
        return "y"
    if name == "z":
        return "z"
    return None


def _image_channel_from_output_socket(socket) -> Optional[str]:
    """Map an image texture output socket to a logical channel token."""
    if socket is None:
        return None
    name = (getattr(socket, "name", None) or "").lower()
    if name == "alpha":
        return "a"
    return None


def _is_identity_math(operation: str, value: Optional[float], linked_index: int) -> bool:
    """Return True when a math node is effectively a pass-through."""
    if value is None:
        return False
    if operation == "ADD" and abs(value) < 1e-6:
        return True
    if operation == "SUBTRACT" and linked_index == 0 and abs(value) < 1e-6:
        return True
    if operation == "MULTIPLY" and abs(value - 1.0) < 1e-6:
        return True
    if operation == "DIVIDE" and linked_index == 0 and abs(value - 1.0) < 1e-6:
        return True
    return False


def _get_manifest() -> Dict[str, Any]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        try:
            _MANIFEST_CACHE = load_manifest()
        except Exception:
            _MANIFEST_CACHE = {}
    return _MANIFEST_CACHE or {}


def _nodedef_for(
    node_name: str,
    output_type: Optional[str] = None,
    input_type: Optional[str] = None,
) -> str:
    """Resolve a manifest nodedef name, failing closed on an impossible ask.

    This used to return the bare node name when the selector found nothing,
    and every consumer treats a non-None result as success - so the bare name
    flowed through the graph builder into an authored info:id that exists in
    no MaterialX library, with ok: true and no diagnostic. Raising here lands
    in the per-material failure handling in rewrite.py, which names the
    material and fails the export loudly instead.
    """
    manifest = _get_manifest()
    nodedef = select_nodedef_name_for_node(
        manifest,
        node_name,
        input_type=input_type,
        output_type=output_type,
    )
    if not nodedef:
        wanted = ", ".join(
            part for part in (
                f"input {input_type}" if input_type else "",
                f"output {output_type}" if output_type else "",
            ) if part
        )
        raise ValueError(
            f"No MaterialX nodedef satisfies '{node_name}'"
            + (f" ({wanted})" if wanted else "")
            + ". Bake the material, or simplify the node graph."
        )
    return nodedef


def _make_node_expr(node_id: str, inputs: Dict[str, Any], output: str = "out") -> Dict[str, Any]:
    """Build a node expression, propagating any unresolved child.

    A node whose input could not be resolved cannot itself be authored
    faithfully. The caller used to receive a node expression regardless, and
    only the *top-level* kind was checked for "unresolved"
    (see the resolver loop's unresolved branch), so a nested failure produced
    a graph the builder then quietly dropped the bad child from - the input
    falling back to a nodedef default with no warning anywhere. Every
    multi-input resolver branch had this shape.

    Surfacing the child's own unresolved expression keeps its provenance
    chain, so the warning names the node that actually failed rather than the
    one that happened to wrap it.
    """
    for value in (inputs or {}).values():
        if isinstance(value, dict) and value.get("kind") == "unresolved":
            return value
    return {
        "kind": "node",
        "node_id": node_id,
        "inputs": inputs,
        "output": output,
    }


def _constant_expr(value: Any) -> Dict[str, Any]:
    return {"kind": "constant", "value": value}


def _expr_is_constant(expr: Optional[Dict[str, Any]], value: float) -> bool:
    if not isinstance(expr, dict):
        return False
    if expr.get("kind") != "constant":
        return False
    try:
        return abs(float(expr.get("value")) - float(value)) < 1e-6
    except Exception:
        return False


def _expr_from_socket(
    socket,
    visited,
    channel,
    provenance,
    cache,
    default: Optional[Any] = None,
):
    if socket is None:
        if default is None:
            return None
        return _constant_expr(default)
    if socket.is_linked:
        # ``visited`` is the active ancestry for cycle detection, not a global
        # graph-visited set. Each sibling branch needs its own copy so a shared
        # upstream node in a valid diamond graph can be resolved twice.
        branch_visited = set(visited or ())
        branch_provenance = list(provenance or ())
        return _resolve_socket_value(
            socket,
            branch_visited,
            channel,
            branch_provenance,
            cache,
        )
    value = _socket_default_value(socket)
    if value is None:
        value = default
    if value is None:
        return None
    return _constant_expr(value)


def _default_texcoord_expr(vector_dim: int = 2) -> Dict[str, Any]:
    nodedef = _nodedef_for("texcoord", "vector3" if vector_dim == 3 else "vector2")
    return _make_node_expr(nodedef, {})


# Combining blends the resolver can author as a real MaterialX node instead of
# requiring a bake. Plain 'MIX' is handled separately (it is a pure lerp).
_RESOLVABLE_MIX_BLENDS = {'MULTIPLY', 'ADD', 'SUBTRACT'}


def _mix_node_params(node):
    """Return (blend_type, factor, a_socket, b_socket) for a Mix/MixRGB node.

    ``factor`` is the constant Factor value, or None when it is unset or driven
    by a link (which the resolver cannot fold). Socket lookup handles both the
    legacy MixRGB (Color1/Color2) and the newer Mix (A/B) names.
    """
    blend = (getattr(node, "blend_type", "") or "MIX").upper()
    if not hasattr(node, "inputs"):
        return blend, None, None, None
    fac_socket = node.inputs.get('Fac') or node.inputs.get('Factor')
    fac = None
    if fac_socket and not fac_socket.is_linked:
        try:
            fac = float(fac_socket.default_value)
        except Exception:
            fac = None
    a_socket = node.inputs.get('Color1') or node.inputs.get('A')
    b_socket = node.inputs.get('Color2') or node.inputs.get('B')
    return blend, fac, a_socket, b_socket


def _is_identity_mix(node) -> bool:
    """Return True when a Mix/MixRGB node is a pure passthrough of one input."""
    if not node or getattr(node, "type", "") not in {'MIX', 'MIX_RGB'}:
        return False
    blend, fac, a_socket, b_socket = _mix_node_params(node)
    if fac is None:
        return False
    # out = lerp(A, op(A, B), fac): Factor 0 is always A; Factor 1 is B only
    # for a plain mix (other blends compute op(A, B), not B).
    if fac == 0.0:
        return bool(a_socket and a_socket.is_linked)
    if fac == 1.0 and blend == 'MIX':
        return bool(b_socket and b_socket.is_linked)
    return False


def _is_supported_mix(node) -> bool:
    """Return True when the resolver can express a Mix/MixRGB node for RCP.

    Either a pure passthrough, or a combining blend (multiply/add/subtract) /
    general plain mix whose inputs are both linked - those are authored as real
    MaterialX nodes, so they do not require baking.
    """
    if _is_identity_mix(node):
        return True
    if not node or getattr(node, "type", "") not in {'MIX', 'MIX_RGB'}:
        return False
    blend, fac, a_socket, b_socket = _mix_node_params(node)
    if fac is None:
        return False
    both_linked = bool(a_socket and b_socket and a_socket.is_linked and b_socket.is_linked)
    if blend == 'MIX':
        return both_linked
    return blend in _RESOLVABLE_MIX_BLENDS and both_linked


def _is_identity_math_node(node) -> bool:
    """Return True when a Math node is effectively a pass-through."""
    if not node or getattr(node, "type", "") != 'MATH':
        return False
    if not hasattr(node, "inputs") or len(node.inputs) < 2:
        return False
    operation = (getattr(node, "operation", "") or "").upper()
    in0 = node.inputs[0]
    in1 = node.inputs[1]

    if in0 and in0.is_linked and (not in1 or not in1.is_linked):
        try:
            value = float(in1.default_value)
        except Exception:
            value = None
        return _is_identity_math(operation, value, linked_index=0)

    if in1 and in1.is_linked and (not in0 or not in0.is_linked):
        try:
            value = float(in0.default_value)
        except Exception:
            value = None
        return _is_identity_math(operation, value, linked_index=1)

    return False


def _extract_mapping_from_node(node) -> Optional[Dict[str, Any]]:
    """Extract mapping transform data from a Mapping node chain."""
    if not node:
        return None

    if node.type == 'REROUTE':
        input_socket = node.inputs[0] if getattr(node, "inputs", None) else None
        if input_socket and input_socket.is_linked:
            return _extract_mapping_from_node(input_socket.links[0].from_node)
        return None

    if node.type == 'MAPPING':
        vector_type = (getattr(node, "vector_type", "POINT") or "POINT").upper()
        if vector_type not in {"POINT", "TEXTURE"}:
            raise ValueError(
                f"Mapping node '{getattr(node, 'name', 'Mapping')}' uses unsupported "
                f"vector_type={vector_type}; bake the texture transform"
            )

        def constant_vector(socket_name: str, legacy_name: str, fallback):
            socket = node.inputs.get(socket_name) if hasattr(node, "inputs") else None
            if socket is not None:
                if socket.is_linked:
                    raise ValueError(
                        f"Mapping node '{getattr(node, 'name', 'Mapping')}' has linked "
                        f"{socket_name}; bake the texture transform"
                    )
                value = getattr(socket, "default_value", fallback)
            else:
                value = getattr(node, legacy_name, fallback)
            return tuple(float(component) for component in value[:3])

        translation = constant_vector("Location", "translation", (0.0, 0.0, 0.0))
        rotation = constant_vector("Rotation", "rotation", (0.0, 0.0, 0.0))
        scale = constant_vector("Scale", "scale", (1.0, 1.0, 1.0))
        if abs(rotation[0]) > 1e-6 or abs(rotation[1]) > 1e-6:
            raise ValueError(
                f"Mapping node '{getattr(node, 'name', 'Mapping')}' has X/Y rotation; "
                "RealityKit place2d can only represent Z rotation"
            )
        if abs(scale[0]) <= 1e-8 or abs(scale[1]) <= 1e-8:
            raise ValueError(
                f"Mapping node '{getattr(node, 'name', 'Mapping')}' has zero X/Y scale; "
                "MaterialX place2d cannot represent it safely"
            )

        if vector_type == "POINT":
            # Blender POINT: rotate(uv * scale) + location. MaterialX place2d
            # SRT implements rotate(uv / scale) - offset.
            place_scale = (1.0 / float(scale[0]), 1.0 / float(scale[1]))
            place_offset = (-float(translation[0]), -float(translation[1]))
            place_rotate = float(rotation[2])
            operation_order = 0
        else:
            # Blender TEXTURE applies the *inverse* transform:
            # rotate(-r)(uv - location) / scale. Measured on Blender 5.2 by
            # baking the mapped coordinate itself - at rotation Z=90 deg, POINT
            # sends (0.9, 0.06) to (-0.06, 0.9) while TEXTURE sends it to
            # (0.06, -0.9), which is rotate(-90). place2d TRS is
            # rotate(theta)(uv - offset)/scale, so theta must be negated here.
            # Only the offset sign used to flip between the two branches, which
            # mirrored a tiled decal's rotation about its pivot.
            place_scale = (float(scale[0]), float(scale[1]))
            place_offset = (float(translation[0]), float(translation[1]))
            place_rotate = -float(rotation[2])
            operation_order = 1
        return {
            'offset': place_offset,
            'rotate': place_rotate,
            'scale': place_scale,
            'pivot': (0.0, 0.0),
            'operationorder': operation_order,
        }

    if node.type == 'TEX_COORD':
        return None

    if node.type == 'UVMAP':
        return None

    return None


def _extract_uv_map_from_node(node) -> Optional[str]:
    """Trace UV map name from a Blender vector node chain."""
    if not node:
        return None

    if node.type == 'UVMAP':
        return getattr(node, "uv_map", "") or ""

    if node.type == 'MAPPING':
        vector_socket = node.inputs.get("Vector")
        if vector_socket and vector_socket.is_linked:
            return _extract_uv_map_from_node(vector_socket.links[0].from_node)

    if node.type == 'TEX_COORD':
        # Assume UV output when explicitly linked to a UV map chain.
        return "UV0"

    return None


def _normalize_uv_map_name(uv_map: Optional[str]) -> str:
    """Normalize Blender UV map names to MaterialX geomprop names."""
    name = (uv_map or "").strip()
    if not name:
        return "UV0"
    lowered = name.lower()
    if lowered in {"uvmap", "uv0", "uv", "st", "st0"}:
        return "UV0"
    return name


def _curve_knots_from_curve(curve) -> List[List[float]]:
    """Extract curve knots from a Blender curve mapping."""
    if not curve:
        return []
    points = getattr(curve, "points", None)
    if not points:
        return []
    knots = []
    for point in points:
        loc = getattr(point, "location", None)
        if not loc:
            continue
        try:
            x = float(loc[0])
            y = float(loc[1])
        except Exception:
            continue
        knots.append([x, y])
    knots.sort(key=lambda item: item[0])
    return knots


def _curve_is_identity(knots: List[List[float]], epsilon: float = 1e-4) -> bool:
    """Return True if curve points lie on the identity line."""
    if not knots:
        return True
    for x, y in knots:
        if abs(x - y) > epsilon:
            return False
    return True


def _normalize_colorspace(name: Optional[str]) -> Optional[str]:
    """Normalize only color spaces verified in Blender 5.2 MaterialX output."""
    if not name:
        return None
    lowered = str(name).strip().lower()
    if lowered in {"srgb", "srgb texture", "s-rgb"}:
        return "srgb"
    if "non-color" in lowered or "raw" in lowered:
        return "raw"
    if lowered in {
        "linear rec.709",
        "linear rec709",
        "linear rec. 709",
        "scene_linear",
        "linear",
    }:
        return "lin_rec709"
    # Keep the original name visible so the USD authoring stage can fail
    # closed instead of inventing an unverified MaterialX token.
    return f"unsupported:{str(name).strip()}"


def _extract_constant_from_socket(socket):
    """Extract a constant value from Blender scalar/color/vector nodes."""
    if not socket or not socket.is_linked:
        return None
    from_node = socket.links[0].from_node
    if not from_node:
        return None

    if from_node.type == 'RGB':
        output = from_node.outputs.get('Color') if hasattr(from_node.outputs, 'get') else None
        value = output.default_value if output else from_node.outputs[0].default_value
        return list(value)[:3]

    if from_node.type == 'VALUE':
        output = from_node.outputs.get('Value') if hasattr(from_node.outputs, 'get') else None
        value = output.default_value if output else from_node.outputs[0].default_value
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if from_node.type in {'INPUT_BOOL', 'INPUT_INT', 'INPUT_VECTOR'}:
        return _input_constant_node_value(from_node)

    return None


def _input_constant_node_value(node):
    """Read Blender 5.2 FunctionNode constants from their node properties.

    The display output socket retains its type default; the artist-authored
    value lives on ``boolean``, ``integer``, or ``vector`` instead.
    """
    node_type = getattr(node, "type", "")
    try:
        if node_type == 'INPUT_BOOL':
            return bool(node.boolean)
        if node_type == 'INPUT_INT':
            return int(node.integer)
        if node_type == 'INPUT_VECTOR':
            dimensions = int(getattr(node, "vector_dimensions", len(node.vector)))
            dimensions = max(2, min(4, dimensions))
            return [float(component) for component in list(node.vector)[:dimensions]]
    except (AttributeError, TypeError, ValueError):
        return None
    return None


def _coerce_constant_value(value: Any, expected: str):
    """Coerce a constant to the expected type."""
    if expected == 'float':
        if isinstance(value, (list, tuple)):
            return float(value[0]) if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if isinstance(value, (list, tuple)):
        if len(value) >= 3:
            return [float(value[0]), float(value[1]), float(value[2])]
        if len(value) == 1:
            return [float(value[0])] * 3
    try:
        return [float(value)] * 3
    except (TypeError, ValueError):
        return [1.0, 1.0, 1.0]


def _resolve_image_path(image) -> Optional[str]:
    """Resolve a Blender image path to an absolute filesystem path."""
    if not image:
        return None

    filepath = image.filepath or image.filepath_raw or ""
    is_dirty = bool(getattr(image, "is_dirty", False))
    packed = getattr(image, "packed_file", None)
    source = (getattr(image, "source", "") or "").upper()

    if is_dirty and source in {"TILED", "SEQUENCE", "MOVIE"}:
        raise ValueError(
            f"Dirty {source.lower()} image '{getattr(image, 'name', 'Image')}' must be "
            "baked to a single current frame before RealityKit export"
        )

    try:
        import bpy
        if filepath:
            filepath = bpy.path.abspath(filepath)
    except Exception:
        pass

    if filepath:
        try:
            filepath = str(Path(filepath).resolve())
        except Exception:
            filepath = os.path.normpath(filepath)

    # A Blender datablock pointer alone is not an image identity. Blender may
    # reuse it after a reload, and a dirty image can become a clean file-backed
    # image without changing the pointer. Include the resolved source state so
    # only an exact image/file version can reuse a staged snapshot.
    cache_key = _image_cache_key(image, filepath)
    cached_path = _STAGED_IMAGE_CACHE.get(cache_key)
    if (
        cached_path
        and not is_dirty
        and packed is None
        and source != "GENERATED"
        and _is_path_on_disk(cached_path)
    ):
        return cached_path

    # Current Blender pixels and packed bytes are authoritative. Never return
    # an external file first for dirty/packed/generated images.
    if is_dirty or packed is not None or source == "GENERATED":
        return _stage_image_to_temp(
            image,
            filepath,
            force_refresh=is_dirty,
            refresh_packed=packed is not None and not is_dirty,
        )

    if filepath and _is_path_on_disk(filepath) and not _is_temp_path(filepath):
        return filepath

    # Fallback: stage packed or generated images to a temp directory.
    return _stage_image_to_temp(image, filepath)


def _is_path_on_disk(path: str) -> bool:
    """Return True if the path exists on disk."""
    try:
        return Path(path).is_file()
    except Exception:
        return False


def _is_temp_path(path: str) -> bool:
    """Return True if the path points into a temporary directory."""
    lowered = path.replace("\\", "/").lower()
    if "usd_textures_tmp" in lowered:
        return True

    temp_root = Path(tempfile.gettempdir())
    try:
        return Path(path).resolve().is_relative_to(temp_root.resolve())
    except Exception:
        return lowered.startswith(str(temp_root).replace("\\", "/").lower())


def _stage_image_to_temp(
    image,
    filepath: Optional[str],
    force_refresh: bool = False,
    refresh_packed: bool = False,
) -> Optional[str]:
    """Stage image data to a temp file so it can be copied into the export."""
    cache_key = _image_cache_key(image, filepath)
    if not force_refresh and not refresh_packed and cache_key in _STAGED_IMAGE_CACHE:
        cached_path = _STAGED_IMAGE_CACHE[cache_key]
        if _is_path_on_disk(cached_path):
            return cached_path
        _STAGED_IMAGE_CACHE.pop(cache_key, None)

    staging_dir = _get_staging_dir()
    source = (getattr(image, "source", "") or "").upper()
    if force_refresh or source == "GENERATED":
        extension = ".exr" if bool(getattr(image, "is_float", False)) else ".png"
    else:
        extension = _guess_image_extension(image, filepath)
    basename = _sanitize_texture_name(Path(filepath).stem if filepath else image.name)
    destination_key = _image_destination_key(image, filepath)
    digest = hashlib.sha256(repr(destination_key).encode("utf-8")).hexdigest()[:12]
    dest_path = staging_dir / f"{basename}_{digest}{extension}"

    if force_refresh:
        if _save_current_image_snapshot_to_path(image, dest_path):
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        raise ValueError(
            f"Unable to snapshot current pixels for dirty image "
            f"'{getattr(image, 'name', 'Image')}'; refusing stale packed or disk bytes"
        )

    if source == "GENERATED":
        if _save_current_image_snapshot_to_path(image, dest_path):
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        raise ValueError(
            f"Unable to snapshot generated image '{getattr(image, 'name', 'Image')}'; "
            "refusing non-current fallback bytes"
        )

    packed = getattr(image, "packed_file", None)
    if packed:
        packed_data = getattr(packed, "data", None)
        if not packed_data:
            raise ValueError(
                f"Packed image '{getattr(image, 'name', 'Image')}' has no readable bytes; "
                "refusing stale external-file fallback"
            )
        try:
            dest_path.write_bytes(packed_data)
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        except Exception as exc:
            raise ValueError(
                f"Unable to stage authoritative packed bytes for image "
                f"'{getattr(image, 'name', 'Image')}'; refusing stale external-file fallback"
            ) from exc

    if filepath and _is_path_on_disk(filepath):
        try:
            shutil.copy2(filepath, dest_path)
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        except Exception:
            pass

    if _save_image_to_path(image, dest_path):
        _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
        return str(dest_path)

    return None


def _save_current_image_snapshot_to_path(image, dest_path: Path) -> bool:
    """Save current in-memory pixels without mutating the source datablock."""
    try:
        import bpy

        width, height = (int(value) for value in image.size[:2])
        if width <= 0 or height <= 0:
            return False
        source_pixels = getattr(image, "pixels", None)
        if source_pixels is None:
            return False

        values = array('f', [0.0]) * len(source_pixels)
        source_pixels.foreach_get(values)
        snapshot = bpy.data.images.new(
            name=f"__BlenderToRCP_{getattr(image, 'name', 'Image')}",
            width=width,
            height=height,
            alpha=True,
            float_buffer=bool(getattr(image, "is_float", False)),
        )
        try:
            # Blender 5.2 can clear a newly assigned pixel buffer when its
            # colorspace is set afterward, even when assigning the same name.
            # Configure metadata before copying the authoritative pixels.
            try:
                snapshot.colorspace_settings.name = image.colorspace_settings.name
            except Exception:
                pass
            try:
                snapshot.alpha_mode = image.alpha_mode
            except Exception:
                pass
            snapshot.pixels.foreach_set(values)
            snapshot.update()
            snapshot.filepath_raw = str(dest_path)
            snapshot.file_format = _EXTENSION_TO_FORMAT.get(dest_path.suffix.lower(), "PNG")
            snapshot.save()
            return dest_path.is_file()
        finally:
            bpy.data.images.remove(snapshot)
    except Exception:
        return False


def _image_cache_key(image, resolved_filepath: Optional[str] = None):
    """Return an export-local key for the current image source state.

    ``Image.as_pointer()`` identifies a live datablock, not its pixels. The
    same pointer survives dirty-to-clean transitions and reloads, and may be
    reused after a datablock is removed. File identity and mutable Blender
    source state therefore participate in the key as well.
    """
    pointer = None
    if hasattr(image, "as_pointer"):
        try:
            pointer = int(image.as_pointer())
        except Exception:
            pass
    if pointer is None:
        pointer = id(image)

    filepath = str(
        resolved_filepath
        or getattr(image, "filepath", "")
        or getattr(image, "filepath_raw", "")
        or ""
    )
    file_state = _file_state_fingerprint(filepath)
    size = getattr(image, "size", ()) or ()
    try:
        dimensions = tuple(int(value) for value in size[:2])
    except Exception:
        dimensions = ()
    packed = getattr(image, "packed_file", None)
    library = getattr(image, "library", None)
    library_path = str(getattr(library, "filepath", "") or "")

    return (
        pointer,
        str(getattr(image, "name", "") or ""),
        str(getattr(image, "source", "") or "").upper(),
        bool(getattr(image, "is_dirty", False)),
        bool(packed is not None),
        str(getattr(image, "filepath_raw", "") or ""),
        filepath,
        file_state,
        dimensions,
        bool(getattr(image, "is_float", False)),
        str(getattr(image, "file_format", "") or ""),
        library_path,
    )


def _file_state_fingerprint(filepath: str):
    """Return enough filesystem identity to invalidate a reloaded source."""
    if not filepath:
        return None
    try:
        stat_result = Path(filepath).stat()
    except (OSError, ValueError):
        return None
    return (
        int(getattr(stat_result, "st_dev", 0)),
        int(getattr(stat_result, "st_ino", 0)),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
    )


def _image_destination_key(image, resolved_filepath: Optional[str]):
    """Return a stable filename identity separate from cache invalidation.

    Pointer and file-stat state belong in the cache key, but putting them in a
    staged filename would make otherwise identical exports nondeterministic.
    A cache miss always rewrites this file, so a stable image/source identity
    remains safe across reloads and dirty-state transitions.
    """
    size = getattr(image, "size", ()) or ()
    try:
        dimensions = tuple(int(value) for value in size[:2])
    except Exception:
        dimensions = ()
    library = getattr(image, "library", None)
    return (
        str(getattr(image, "name", "") or ""),
        str(getattr(image, "source", "") or "").upper(),
        str(getattr(image, "filepath_raw", "") or resolved_filepath or ""),
        str(getattr(library, "filepath", "") or ""),
        dimensions,
        bool(getattr(image, "is_float", False)),
        str(getattr(image, "file_format", "") or ""),
    )


def begin_image_staging_session(diagnostics=None) -> Path:
    """Start a unique image-staging session for one export.

    Any abandoned previous session is removed first. A unique directory avoids
    reusing files left by an earlier export in the same long-lived Blender
    process, while clearing the cache prevents datablock-pointer reuse.
    """
    global _STAGED_IMAGE_DIR, _STAGED_IMAGE_DIR_OWNED
    cleanup_image_staging_session(diagnostics)
    base_dir = Path(tempfile.gettempdir()) / "blendertorcp_textures"
    base_dir.mkdir(parents=True, exist_ok=True)
    _STAGED_IMAGE_DIR = Path(
        tempfile.mkdtemp(prefix=f"export_{os.getpid()}_", dir=str(base_dir))
    )
    _STAGED_IMAGE_DIR_OWNED = True
    _STAGED_IMAGE_CACHE.clear()
    return _STAGED_IMAGE_DIR


def cleanup_image_staging_session(diagnostics=None) -> bool:
    """Clear image cache state and remove the current owned temp directory."""
    global _STAGED_IMAGE_DIR, _STAGED_IMAGE_DIR_OWNED
    staging_dir = _STAGED_IMAGE_DIR
    owned = _STAGED_IMAGE_DIR_OWNED
    _STAGED_IMAGE_CACHE.clear()
    _STAGED_IMAGE_DIR = None
    _STAGED_IMAGE_DIR_OWNED = False

    if staging_dir is None or not owned:
        return True
    try:
        shutil.rmtree(staging_dir)
    except FileNotFoundError:
        pass
    except OSError as exc:
        if diagnostics and hasattr(diagnostics, "add_warning"):
            diagnostics.add_warning(
                f"Failed to remove temporary image staging directory "
                f"'{staging_dir}': {exc}"
            )
        return False

    try:
        staging_dir.parent.rmdir()
    except OSError:
        pass
    return not staging_dir.exists()


def _get_staging_dir() -> Path:
    """Return the staging directory for temporary textures."""
    if _STAGED_IMAGE_DIR is None:
        return begin_image_staging_session()
    _STAGED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return _STAGED_IMAGE_DIR


def _sanitize_texture_name(name: str) -> str:
    """Sanitize a filename stem for staging."""
    if not name:
        return "image"
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    if sanitized[0].isdigit():
        sanitized = f"img_{sanitized}"
    return sanitized


def _guess_image_extension(image, filepath: Optional[str]) -> str:
    """Return a best-effort extension for the image."""
    if filepath:
        ext = Path(filepath).suffix.lower()
        if ext in _EXTENSION_TO_FORMAT:
            return ext
    fmt = getattr(image, "file_format", None)
    if fmt:
        return _FORMAT_TO_EXTENSION.get(str(fmt).upper(), ".png")
    return ".png"


def _save_image_to_path(image, dest_path: Path) -> bool:
    """Attempt to save an image to disk without mutating the original path."""
    try:
        orig_path = image.filepath_raw
        orig_format = image.file_format
    except Exception:
        orig_path = None
        orig_format = None

    try:
        fmt = _EXTENSION_TO_FORMAT.get(dest_path.suffix.lower(), "PNG")
        image.filepath_raw = str(dest_path)
        if fmt:
            image.file_format = fmt
        image.save()
        return dest_path.exists()
    except Exception:
        try:
            image.save_render(str(dest_path))
            return dest_path.exists()
        except Exception:
            return False
    finally:
        try:
            if orig_path is not None:
                image.filepath_raw = orig_path
            if orig_format is not None:
                image.file_format = orig_format
        except Exception:
            pass
