"""
Blender material extraction for RealityKit export.

Extracts supported parameters and emits warnings for unsupported nodes.
"""

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ....manifest.materialx_nodes import load_manifest, select_nodedef_name_for_node

_MANIFEST_CACHE: Optional[Dict[str, Any]] = None
_STAGED_IMAGE_CACHE: Dict[int, str] = {}
_STAGED_IMAGE_DIR: Optional[Path] = None

_FORMAT_TO_EXTENSION = {
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


def extract_blender_material_data(material) -> Dict[str, Any]:
    """Extract supported material parameters from a Blender material."""
    data = {
        'name': material.name,
        'type': 'unknown',
    }
    data['blend_method'] = getattr(material, "blend_method", "OPAQUE")

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
        for node in material.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                principled = node
                break

    if principled:
        data['type'] = 'principled'
        resolve_cache = {}
        unresolved_warnings: List[str] = []
        input_graphs: Dict[str, Any] = {}

        graph_input_map = {
            'Base Color': 'baseColor',
            'Metallic': 'metallic',
            'Roughness': 'roughness',
            'Specular': 'specular',
            'Specular IOR Level': 'specular',
            'Normal': 'normal',
            'Alpha': 'opacity',
            'Emission Color': 'emissiveColor',
            'Emission': 'emissiveColor',
        }
        expected_type_map = {
            'Base Color': 'color3',
            'Metallic': 'float',
            'Roughness': 'float',
            'Specular': 'float',
            'Specular IOR Level': 'float',
            'Normal': 'vector3',
            'Alpha': 'float',
            'Emission Color': 'color3',
            'Emission': 'color3',
        }

        base_color_socket = principled.inputs.get('Base Color')
        metallic_socket = principled.inputs.get('Metallic')
        roughness_socket = principled.inputs.get('Roughness')
        specular_socket = principled.inputs.get('Specular') or principled.inputs.get('Specular IOR Level')
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

        emission_color_socket = principled.inputs.get('Emission Color') or principled.inputs.get('Emission')
        emission_strength_socket = principled.inputs.get('Emission Strength')
        if emission_color_socket and emission_strength_socket:
            emission_color = list(emission_color_socket.default_value)[:3]
            emission_strength = emission_strength_socket.default_value
            if emission_strength > 0:
                data['emission_color'] = [c * emission_strength for c in emission_color]
                data['emission_strength'] = emission_strength

        clearcoat_socket = principled.inputs.get('Clearcoat')
        clearcoat_roughness_socket = principled.inputs.get('Clearcoat Roughness')
        if clearcoat_socket:
            data['clearcoat'] = clearcoat_socket.default_value
        if clearcoat_roughness_socket:
            data['clearcoat_roughness'] = clearcoat_roughness_socket.default_value

        if material.blend_method in {'CLIP', 'HASHED'}:
            data['alpha_threshold'] = material.alpha_threshold

        texture_map = {
            'Base Color': 'base_color_texture',
            'Metallic': 'metallic_texture',
            'Roughness': 'roughness_texture',
            'Normal': 'normal_texture',
            'Alpha': 'alpha_texture',
            'Clearcoat Normal': 'clearcoat_normal_texture',
            'Emission Color': 'emission_texture',
            'Emission': 'emission_texture',
        }
        constant_map = {
            'Base Color': ('base_color', 'color'),
            'Metallic': ('metallic', 'float'),
            'Roughness': ('roughness', 'float'),
            'Specular': ('specular', 'float'),
            'Specular IOR Level': ('specular', 'float'),
            'Alpha': ('alpha', 'float'),
            'Emission Color': ('emission_color', 'color'),
            'Emission': ('emission_color', 'color'),
            'Emission Strength': ('emission_strength', 'float'),
            'Clearcoat': ('clearcoat', 'float'),
            'Clearcoat Roughness': ('clearcoat_roughness', 'float'),
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
                    if alpha_mode == 'premul':
                        data['has_premultiplied_alpha'] = True
                scale = resolved.get("scale")
                if scale is not None:
                    data[f"{texture_key}_scale"] = scale
                space = resolved.get("space")
                if space:
                    data[f"{texture_key}_space"] = space
                if input_name == 'Base Color':
                    data.pop('base_color', None)
                continue

            if resolved and resolved.get("kind") == "node":
                target_input = graph_input_map.get(input_name)
                if target_input:
                    input_graphs[target_input] = resolved
                    continue

            if resolved and resolved.get("kind") == "constant" and input_name in constant_map:
                key, expected = constant_map[input_name]
                data[key] = _coerce_constant_value(resolved["value"], expected)
                continue

            if resolved and resolved.get("kind") == "unresolved":
                chain = resolved.get("provenance") or []
                if chain:
                    unresolved_warnings.append(
                        f"Material '{material.name}': Unable to resolve '{input_name}' "
                        f"through chain: {' -> '.join(chain)}"
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
        if input_graphs:
            data['input_graphs'] = input_graphs

    else:
        emission_node = None
        if surface_node and surface_node.type == 'EMISSION':
            emission_node = surface_node
        else:
            emission_nodes = [n for n in material.node_tree.nodes if n.type == 'EMISSION']
            if emission_nodes:
                emission_node = emission_nodes[0]

        if emission_node:
            data['type'] = 'emission'
            color_socket = emission_node.inputs.get('Color')
            strength_socket = emission_node.inputs.get('Strength')
            if color_socket:
                if color_socket.is_linked:
                    texture_path = _extract_image_path_from_socket(color_socket)
                    if texture_path:
                        data['base_color_texture'] = texture_path
                    else:
                        constant = _extract_constant_from_socket(color_socket)
                        if constant is not None:
                            data['base_color'] = _coerce_constant_value(constant, 'color')
                else:
                    data['base_color'] = list(color_socket.default_value)[:3]
            if strength_socket:
                if strength_socket.is_linked:
                    constant = _extract_constant_from_socket(strength_socket)
                    if constant is not None:
                        data['emission_strength'] = _coerce_constant_value(constant, 'float')
                    else:
                        data['emission_strength'] = strength_socket.default_value
                else:
                    data['emission_strength'] = strength_socket.default_value

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

    supported_types = {
        'OUTPUT_MATERIAL',
        'BSDF_PRINCIPLED',
        'EMISSION',
        'TEX_IMAGE',
        'NORMAL_MAP',
        'RGB',
        'VALUE',
        'SEPARATE_COLOR',
        'SEPARATE_RGB',
        'SEPARATE_XYZ',
        'SEPXYZ',
    }

    partial_types = {
        'TEX_COORD',
        'UVMAP',
        'MAPPING',
    }

    bake_types = {
        'BUMP',
        'DISPLACEMENT',
        'VECTOR_DISPLACEMENT',
        'TEX_WAVE',
        'TEX_WHITE_NOISE',
        'TEX_MAGIC',
        'TEX_CHECKER',
        'TEX_BRICK',
        'TEX_POINTDENSITY',
        'TEX_SKY',
        'TEX_GABOR',
        'TEX_IES',
        'BLACKBODY',
        'LIGHT_FALLOFF',
        'WAVELENGTH',
        'VECTOR_MATH',
        'CURVE_RGB',
        'INVERT',
        'GAMMA',
        'SHADER_TO_RGB',
        'COMBXYZ',
        'CURVE_VEC',
        'RADIAL_TILING',
        'COMBINE_CYLINDRICAL',
        'SEPARATE_CYLINDRICAL',
        'COMBINE_SPHERICAL',
        'SEPARATE_SPHERICAL',
        'FLOAT_CURVE',
    }

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
            continue

        if node_type in {'MIX_RGB', 'MIX'}:
            if _is_identity_mix(node):
                continue
            warnings.append(
                f"Material '{material.name}': Node '{node_name}' ({node_type}) requires baking unless "
                "Factor is 0/1 with a passthrough input."
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


def _find_rk_group_node(material):
    """Find a RealityKit-authored node group in the material."""
    for node in material.node_tree.nodes:
        if node.type != 'GROUP' or not node.node_tree:
            continue
        node_id = node.node_tree.get("rk_node_id")
        if node_id:
            return node
        name = node.node_tree.name or ""
        if name.startswith("RK_"):
            return node
    return None


def _extract_rk_group_material_data(group_node, base_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract inputs from a RealityKit node group."""
    data = dict(base_data)
    graph = _build_rk_node_graph(group_node)
    if graph:
        data['type'] = 'rk_graph'
        data['rk_graph'] = graph
        return data

    node_tree = group_node.node_tree
    node_id = node_tree.get("rk_node_id") if node_tree else None

    if not node_id:
        node_id = _infer_rk_node_id(node_tree.name if node_tree else "")

    data['type'] = 'rk_group'
    data['rk_node_id'] = node_id
    data['rk_inputs'] = _extract_group_inputs(group_node)
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
                        'type': 'texture',
                        'path': texture_path,
                        'output_type': output_type,
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
                        if alpha_mode == 'premul':
                            data['has_premultiplied_alpha'] = True
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

    return {
        "nodes": nodes,
        "connections": connections,
        "output": _node_name(surface_node),
    }


def _extract_group_inputs(group_node) -> Dict[str, Any]:
    """Extract group input values and texture references."""
    inputs = {}
    for socket in group_node.inputs:
        input_name = socket.name
        if socket.is_linked:
            texture_path = _extract_image_path_from_socket(socket)
            if texture_path:
                output_type = _socket_output_type(socket)
                tex_type = 'normal_texture' if _is_normal_socket(socket) else 'texture'
                texture_spec = {
                    'type': tex_type,
                    'path': texture_path,
                    'output_type': output_type,
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
        fac_socket = from_node.inputs.get('Fac') if hasattr(from_node, "inputs") else None
        if fac_socket is None and hasattr(from_node, "inputs"):
            fac_socket = from_node.inputs.get('Factor')
        if fac_socket and not fac_socket.is_linked:
            try:
                fac = float(fac_socket.default_value)
            except Exception:
                fac = None
            a_socket = from_node.inputs.get('Color1') if hasattr(from_node, "inputs") else None
            b_socket = from_node.inputs.get('Color2') if hasattr(from_node, "inputs") else None
            if a_socket is None and hasattr(from_node, "inputs"):
                a_socket = from_node.inputs.get('A')
            if b_socket is None and hasattr(from_node, "inputs"):
                b_socket = from_node.inputs.get('B')
            if fac == 0.0 and a_socket and a_socket.is_linked:
                return _resolve_socket_value(
                    a_socket,
                    visited,
                    channel,
                    provenance,
                    cache,
                    expected_type=expected_type,
                )
            if fac == 1.0 and b_socket and b_socket.is_linked:
                return _resolve_socket_value(
                    b_socket,
                    visited,
                    channel,
                    provenance,
                    cache,
                    expected_type=expected_type,
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
            _nodedef_for("hsvadjust", expected_type or "color3"),
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
        elements = list(getattr(ramp, "elements", []) or [])
        if len(elements) >= 2:
            left = elements[0]
            right = elements[-1]
            left_color = list(left.color)
            right_color = list(right.color)
        else:
            left_color = [0.0, 0.0, 0.0, 1.0]
            right_color = [1.0, 1.0, 1.0, 1.0]
        use_alpha = (left_color[3] < 0.999) or (right_color[3] < 0.999)
        ramp_type = "color4" if use_alpha else "color3"
        ramp_inputs = {
            "valuel": left_color if use_alpha else left_color[:3],
            "valuer": right_color if use_alpha else right_color[:3],
        }
        texcoord_expr = _make_node_expr(
            _nodedef_for("combine2", "vector2"),
            {"in1": fac_expr, "in2": _constant_expr(0.0)},
        )
        ramp_inputs["texcoord"] = texcoord_expr
        return _make_node_expr(_nodedef_for("ramplr", ramp_type), ramp_inputs)

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

        combined_curve = curves[0] if len(curves) > 0 else None
        red_curve = curves[1] if len(curves) > 1 else combined_curve
        green_curve = curves[2] if len(curves) > 2 else combined_curve
        blue_curve = curves[3] if len(curves) > 3 else combined_curve

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

        separate_id = _nodedef_for("separate3", "color3")

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
        return _make_node_expr(_nodedef_for("luminance", "float"), {"in": color_expr})

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

    if node_type == 'TEX_MUSGRAVE':
        vector_expr = _expr_from_socket(
            from_node.inputs.get('Vector') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
        )
        if vector_expr is None:
            vector_expr = _default_texcoord_expr(vector_dim=3)
        detail_expr = _expr_from_socket(
            from_node.inputs.get('Detail') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=2.0,
        )
        lac_expr = _expr_from_socket(
            from_node.inputs.get('Lacunarity') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=2.0,
        )
        dim_expr = _expr_from_socket(
            from_node.inputs.get('Dimension') if hasattr(from_node, "inputs") else None,
            visited,
            channel,
            provenance,
            cache,
            default=0.5,
        )
        node_id = _nodedef_for("fractal3d", "float")
        return _make_node_expr(
            node_id,
            {
                "position": vector_expr,
                "octaves": detail_expr,
                "lacunarity": lac_expr,
                "diminish": dim_expr,
                "amplitude": _constant_expr(1.0),
            },
        )

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
        if expected_type:
            texture_info.setdefault("output_type", expected_type)
        if channel:
            texture_info.setdefault("channel", channel)
        if cache is not None and cache_key is not None:
            cache[cache_key] = dict(texture_info)
        return texture_info

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
    }


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


def _nodedef_for(node_name: str, output_type: Optional[str] = None) -> str:
    manifest = _get_manifest()
    nodedef = select_nodedef_name_for_node(
        manifest,
        node_name,
        output_type=output_type,
    )
    return nodedef or node_name


def _make_node_expr(node_id: str, inputs: Dict[str, Any], output: str = "out") -> Dict[str, Any]:
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
        return _resolve_socket_value(
            socket,
            visited,
            channel,
            provenance,
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


def _is_identity_mix(node) -> bool:
    """Return True when a Mix/MixRGB node is a passthrough."""
    if not node or getattr(node, "type", "") not in {'MIX', 'MIX_RGB'}:
        return False
    if not hasattr(node, "inputs"):
        return False
    fac_socket = node.inputs.get('Fac') or node.inputs.get('Factor')
    if not fac_socket or fac_socket.is_linked:
        return False
    try:
        fac_value = float(fac_socket.default_value)
    except Exception:
        return False

    a_socket = node.inputs.get('Color1') if hasattr(node, "inputs") else None
    b_socket = node.inputs.get('Color2') if hasattr(node, "inputs") else None
    if a_socket is None and hasattr(node, "inputs"):
        a_socket = node.inputs.get('A')
    if b_socket is None and hasattr(node, "inputs"):
        b_socket = node.inputs.get('B')

    if fac_value == 0.0:
        return bool(a_socket and a_socket.is_linked)
    if fac_value == 1.0:
        return bool(b_socket and b_socket.is_linked)
    return False


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

    if node.type == 'MAPPING':
        translation = getattr(node, "translation", (0.0, 0.0, 0.0))
        rotation = getattr(node, "rotation", (0.0, 0.0, 0.0))
        scale = getattr(node, "scale", (1.0, 1.0, 1.0))
        return {
            'offset': (float(translation[0]), float(translation[1])),
            'rotate': float(rotation[2]),
            'scale': (float(scale[0]), float(scale[1])),
            'pivot': (0.0, 0.0),
            'operationorder': 0,
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
    """Normalize Blender colorspace names to simple tags."""
    if not name:
        return None
    lowered = str(name).strip().lower()
    if lowered in {"srgb", "srgb texture", "s-rgb"}:
        return "srgb"
    if "non-color" in lowered or "raw" in lowered:
        return "raw"
    return lowered


def _extract_constant_from_socket(socket):
    """Extract a constant value from linked RGB/Value nodes."""
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


def _stage_image_to_temp(image, filepath: Optional[str]) -> Optional[str]:
    """Stage image data to a temp file so it can be copied into the export."""
    cache_key = _image_cache_key(image)
    if cache_key in _STAGED_IMAGE_CACHE:
        return _STAGED_IMAGE_CACHE[cache_key]

    staging_dir = _get_staging_dir()
    extension = _guess_image_extension(image, filepath)
    basename = _sanitize_texture_name(Path(filepath).stem if filepath else image.name)
    digest = hashlib.sha1(f"{image.name}:{filepath}".encode("utf-8")).hexdigest()[:8]
    dest_path = staging_dir / f"{basename}_{digest}{extension}"

    if dest_path.exists():
        _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
        return str(dest_path)

    if filepath and _is_path_on_disk(filepath):
        try:
            import shutil
            shutil.copy2(filepath, dest_path)
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        except Exception:
            pass

    packed = getattr(image, "packed_file", None)
    if packed and getattr(packed, "data", None):
        try:
            dest_path.write_bytes(packed.data)
            _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
            return str(dest_path)
        except Exception:
            pass

    if _save_image_to_path(image, dest_path):
        _STAGED_IMAGE_CACHE[cache_key] = str(dest_path)
        return str(dest_path)

    return None


def _image_cache_key(image) -> int:
    """Return a stable cache key for an image."""
    if hasattr(image, "as_pointer"):
        try:
            return int(image.as_pointer())
        except Exception:
            pass
    return id(image)


def _get_staging_dir() -> Path:
    """Return the staging directory for temporary textures."""
    global _STAGED_IMAGE_DIR
    if _STAGED_IMAGE_DIR is None:
        base_dir = Path(tempfile.gettempdir()) / "blendertorcp_textures"
        base_dir.mkdir(parents=True, exist_ok=True)
        session_name = f"session_{os.getpid()}"
        staging_dir = base_dir / session_name
        staging_dir.mkdir(parents=True, exist_ok=True)
        _STAGED_IMAGE_DIR = staging_dir
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
