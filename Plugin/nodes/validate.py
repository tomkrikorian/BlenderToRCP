"""
RealityKit material validation and enforcement helpers.
"""

from typing import Dict, List, Optional, Set

from . import metadata


ALLOWED_UI_TYPES = {
    'FRAME',
    'REROUTE',
}

SUPPORTED_TYPES = {
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
    'TEX_NOISE',
    'TEX_VORONOI',
    'TEX_MUSGRAVE',
    'TEX_GRADIENT',
    'TEX_ENVIRONMENT',
    'CLAMP',
    'HUE_SAT',
    'BRIGHTCONTRAST',
    'VALTORGB',
    'RGBTOBW',
    'COMBINE_COLOR',
    'VECTOR_ROTATE',
    'VECTOR_TRANSFORM',
    'NORMAL',
    'MAP_RANGE',
    'INVERT',
    'CURVE_RGB',
}

SHADERGRAPH_SUPPORTED_TYPES = {
}

PARTIAL_TYPES = {
    'TEX_COORD',
    'UVMAP',
    'MAPPING',
}

BAKE_TYPES = {
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

UNSUPPORTED_TYPES = {
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


def validate_material(
    material,
    only_connected: bool = True,
    strict: bool = False,
) -> Dict[str, object]:
    """Validate a Blender material against RealityKit compatibility rules."""
    result = {
        "material": getattr(material, "name", "Unknown"),
        "ok": True,
        "errors": [],
        "warnings": [],
        "offending_nodes": [],
        "warning_nodes": [],
    }

    if not material or not material.use_nodes or not material.node_tree:
        return result

    if only_connected:
        used_nodes = _collect_used_nodes(material)
    else:
        used_nodes = set(material.node_tree.nodes)

    def add_issue(kind: str, node, message: str, force_error: bool = False) -> None:
        target = "errors" if force_error else kind
        _add_issue(result, target, node, message)

    for node in used_nodes:
        node_type = getattr(node, "type", "")
        node_name = getattr(node, "name", node_type)

        if node_type in ALLOWED_UI_TYPES:
            continue

        if node_type == 'GROUP':
            if _is_rk_group(node):
                continue
            add_issue("errors", node, "Non-RealityKit node group used.")
            continue

        if node_type in SUPPORTED_TYPES:
            if node_type == 'TEX_IMAGE' and getattr(node, "image", None) is None:
                add_issue(
                    "warnings",
                    node,
                    "Image Texture node has no image.",
                    force_error=strict,
                )
            continue

        if node_type in SHADERGRAPH_SUPPORTED_TYPES:
            add_issue(
                "errors",
                node,
                "Node is supported by ShaderGraph but not yet mapped by the exporter.",
            )
            continue

        if node_type in {'MIX_RGB', 'MIX'}:
            if _is_identity_mix(node):
                continue
            add_issue(
                "warnings",
                node,
                "Mix node requires baking unless Factor is 0/1 with a passthrough input.",
                force_error=strict,
            )
            continue

        if node_type == 'MATH':
            if _is_identity_math_node(node):
                continue
            add_issue(
                "warnings",
                node,
                "Math node requires baking unless it is a pass-through (add 0, subtract 0, multiply 1, divide 1).",
                force_error=strict,
            )
            continue

        if node_type in PARTIAL_TYPES:
            add_issue(
                "warnings",
                node,
                "Node has limited support; UV mapping is only applied for Image Texture inputs.",
            )
            continue

        if node_type in BAKE_TYPES:
            add_issue(
                "warnings",
                node,
                "Node requires baking for RealityKit.",
                force_error=strict,
            )
            continue

        if node_type in UNSUPPORTED_TYPES:
            add_issue("errors", node, "Node is not supported by RealityKit export.")
            continue

        add_issue("errors", node, "Node type is unrecognized by the exporter.")

    result["ok"] = not result["errors"]
    return result


def validate_materials(
    materials,
    only_connected: bool = True,
    strict: bool = False,
) -> Dict[str, object]:
    """Validate a collection of materials and aggregate issues."""
    summary = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "materials": [],
    }

    for material in materials:
        result = validate_material(material, only_connected=only_connected, strict=strict)
        summary["materials"].append(result)
        summary["errors"].extend(result["errors"])
        summary["warnings"].extend(result["warnings"])

    summary["ok"] = not summary["errors"]
    return summary


def select_offending_nodes(material, issues: Dict[str, object]) -> None:
    """Select offending nodes in a material's node tree."""
    if not material or not material.node_tree:
        return
    offending = issues.get("offending_nodes", []) + issues.get("warning_nodes", [])
    if not offending:
        return
    node_tree = material.node_tree
    for node in node_tree.nodes:
        node.select = False
    active = None
    for entry in offending:
        node = entry.get("node")
        if node and node in node_tree.nodes:
            node.select = True
            active = node
    if active:
        node_tree.nodes.active = active


def remove_offending_nodes(material, issues: Dict[str, object]) -> int:
    """Remove offending nodes from a material's node tree."""
    if not material or not material.node_tree:
        return 0
    offending = issues.get("offending_nodes", [])
    if not offending:
        return 0
    node_tree = material.node_tree
    removed = 0
    for entry in list(offending):
        node = entry.get("node")
        if node and node in node_tree.nodes:
            node_tree.nodes.remove(node)
            removed += 1
    return removed


def collect_scene_materials(context) -> List[object]:
    """Collect materials referenced by objects in the current scene."""
    materials = []
    seen = set()
    for obj in context.scene.objects:
        for slot in getattr(obj, "material_slots", []):
            mat = slot.material
            if mat and mat not in seen:
                seen.add(mat)
                materials.append(mat)
    return materials


def _add_issue(result: Dict[str, object], kind: str, node, message: str) -> None:
    entry = {
        "node_name": getattr(node, "name", ""),
        "node_type": getattr(node, "type", ""),
        "message": message,
        "node": node,
    }
    result[kind].append(entry)
    if kind == "errors":
        result["offending_nodes"].append(entry)
    else:
        result["warning_nodes"].append(entry)


def _is_rk_group(node) -> bool:
    node_tree = getattr(node, "node_tree", None)
    if not node_tree:
        return False
    node_id = node_tree.get("rk_node_id")
    if node_id:
        return True
    name = (node_tree.name or "").lstrip(".")
    return metadata.is_catalog_group_name(name)


def _collect_used_nodes(material) -> Set[object]:
    node_tree = material.node_tree
    used_nodes: Set[object] = set()

    output_nodes = [n for n in node_tree.nodes if n.type == 'OUTPUT_MATERIAL']
    if not output_nodes:
        return used_nodes

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
        for link in socket.links:
            if link.from_node:
                visit(link.from_node)

    used_nodes.add(active_output)
    return used_nodes


def _is_identity_mix(node) -> bool:
    """Return True when a Mix/MixRGB node is a passthrough."""
    if not node or getattr(node, "type", "") not in {'MIX', 'MIX_RGB'}:
        return False
    fac_socket = None
    if hasattr(node, "inputs"):
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


def _is_identity_math(operation: str, value: float | None, linked_index: int) -> bool:
    """Return True when a math node is a passthrough."""
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
