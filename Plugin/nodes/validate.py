"""
RealityKit material validation and enforcement helpers.
"""

from __future__ import annotations

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
    'INPUT_BOOL',
    'INPUT_INT',
    'INPUT_VECTOR',
    'SEPARATE_COLOR',
    'SEPARATE_RGB',
    'SEPARATE_XYZ',
    'SEPXYZ',
    'TEX_NOISE',
    'TEX_VORONOI',
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
    'CURVE_RGB',
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


# Blender 5.2 Principled controls that the portable RealityKit PBR v1 graph
# cannot represent.  The neutral values are Blender 5.2's factory defaults,
# captured from the live node RNA.  Keeping the contract here, beside material
# validation, prevents the graph builder's intentionally small portable subset
# from becoming a silent appearance downgrade.
_PORTABLE_OMITTED_PRINCIPLED_INPUTS = (
    ('Diffuse Roughness', 0.0, 'RealityKit PBR Surface 2 or OpenPBR 1.1', None),
    ('Subsurface Weight', 0.0, 'RealityKit PBR Surface 2 or OpenPBR 1.1', None),
    (
        'Subsurface Radius',
        (1.0, 0.2, 0.1),
        'RealityKit PBR Surface 2 or OpenPBR 1.1',
        'Subsurface Weight',
    ),
    (
        'Subsurface Scale',
        0.005,
        'RealityKit PBR Surface 2 or OpenPBR 1.1',
        'Subsurface Weight',
    ),
    (
        'Subsurface Anisotropy',
        0.0,
        'RealityKit PBR Surface 2 or OpenPBR 1.1',
        'Subsurface Weight',
    ),
    ('IOR', 1.5, 'RealityKit PBR Surface 2 or OpenPBR 1.1', None),
    (
        'Specular Tint',
        (1.0, 1.0, 1.0, 1.0),
        None,
        None,
    ),
    ('Coat IOR', 1.5, 'RealityKit PBR Surface 2 or OpenPBR 1.1', 'Coat Weight'),
    ('Coat Tint', (1.0, 1.0, 1.0, 1.0), 'OpenPBR 1.1', 'Coat Weight'),
    ('Sheen Weight', 0.0, 'RealityKit PBR Surface 2 or OpenPBR 1.1', None),
    ('Sheen Roughness', 0.5, 'OpenPBR 1.1', 'Sheen Weight'),
    (
        'Sheen Tint',
        (1.0, 1.0, 1.0, 1.0),
        'RealityKit PBR Surface 2 or OpenPBR 1.1',
        'Sheen Weight',
    ),
)

# These Blender 5.2 controls currently have no faithful graph path in any
# profile.  OpenPBR's vendored nodedef exposes thin-film inputs, but extraction
# does not author them yet; accepting them in validation would still lose the
# artist's values.  Subsurface IOR is likewise not mapped by either surface.
_UNMAPPED_PRINCIPLED_INPUTS = (
    ('Subsurface IOR', 1.4, 'Subsurface Weight'),
    ('Thin Film Thickness', 0.0, None),
    ('Thin Film IOR', 1.33, 'Thin Film Thickness'),
)


def _values_differ(value, neutral, epsilon: float = 1e-6) -> bool:
    """Compare scalar/vector Blender socket values against a known default."""
    if isinstance(neutral, (tuple, list)):
        try:
            values = list(value)
        except (TypeError, ValueError):
            return True
        if len(values) < len(neutral):
            return True
        try:
            return any(
                abs(float(values[index]) - float(component)) > epsilon
                for index, component in enumerate(neutral)
            )
        except (TypeError, ValueError):
            return True
    try:
        return abs(float(value) - float(neutral)) > epsilon
    except (TypeError, ValueError):
        return value != neutral


def _unsupported_principled_inputs(
    node,
    surface_profile: str = "realitykit_portable",
) -> List[str]:
    """Report Principled BSDF inputs that RealityKit PBR cannot represent.

    Only inputs that are linked or deviate from their neutral default are
    reported, so a stock Principled node stays silent.
    """
    issues: List[str] = []

    def _socket(name: str):
        return node.inputs.get(name)

    def _linked(name: str) -> bool:
        socket = _socket(name)
        return bool(socket is not None and getattr(socket, 'is_linked', False))

    def _active(name: str, neutral=0.0) -> bool:
        socket = node.inputs.get(name)
        if socket is None:
            return False
        if getattr(socket, 'is_linked', False):
            return True
        return _values_differ(getattr(socket, 'default_value', None), neutral)

    subsurface_active = _active('Subsurface Weight')
    coat_active = _active('Coat Weight')
    sheen_active = _active('Sheen Weight')
    transmission_active = _active('Transmission Weight')
    thin_film_active = _active('Thin Film Thickness')
    anisotropy_active = _active('Anisotropic')

    thin_wall = node.inputs.get('Thin Wall')
    if (
        thin_wall is not None
        and (getattr(thin_wall, 'is_linked', False) or bool(thin_wall.default_value))
        and (transmission_active or subsurface_active)
    ):
        issues.append("Principled 'Thin Wall' is enabled; RealityKit has no thin-wall shading.")
    if transmission_active:
        issues.append("Principled 'Transmission Weight' is not exportable; the material will be opaque.")

    profile = (surface_profile or 'realitykit_portable').strip().lower()

    # Coat constants are mapped, but linked Coat Weight/Roughness/Tint values
    # have no graph_input_map entry in extraction.  Reject those links in every
    # profile until they can be preserved rather than accepting a default value.
    linked_coat_inputs = {
        name
        for name in ('Coat Weight', 'Coat Roughness', 'Coat Tint')
        if _linked(name) and (name == 'Coat Weight' or coat_active)
    }
    for name in sorted(linked_coat_inputs):
        issues.append(
            f"Principled '{name}' is linked, but linked coat controls are not exportable; "
            "bake the material or use an unlinked constant."
        )

    # Blender's anisotropy level and rotation do not map one-to-one to the
    # currently authored PBR2/OpenPBR inputs: native Blender 5.2 applies a level
    # factor and tangent rotation that this exporter does not reproduce.  A
    # partially mapped result is worse than an actionable failure.
    anisotropy_inputs = (
        ('Anisotropic', 0.0, None),
        ('Anisotropic Rotation', 0.0, 'Anisotropic'),
        ('Tangent', (0.0, 0.0, 0.0), 'Anisotropic'),
    )
    for name, neutral, controller in anisotropy_inputs:
        if (controller is None or anisotropy_active) and _active(name, neutral):
            issues.append(
                f"Principled '{name}' requires a verified Blender 5.2 tangent/anisotropy "
                "mapping; bake the material before export."
            )

    active_controllers = {
        'Subsurface Weight': subsurface_active,
        'Coat Weight': coat_active,
        'Sheen Weight': sheen_active,
        'Thin Film Thickness': thin_film_active,
    }

    for name, neutral, controller in _UNMAPPED_PRINCIPLED_INPUTS:
        if (
            (controller is None or active_controllers.get(controller, False))
            and _active(name, neutral)
        ):
            issues.append(
                f"Principled '{name}' is not authored by the selected MaterialX profiles; "
                "bake the material before export."
            )

    if profile == 'realitykit_portable':
        for name, neutral, alternative, controller in _PORTABLE_OMITTED_PRINCIPLED_INPUTS:
            # A linked Coat Tint was already reported by the graph-map gate.
            if name in linked_coat_inputs:
                continue
            if (
                (controller is None or active_controllers.get(controller, False))
                and _active(name, neutral)
            ):
                remediation = (
                    f"select {alternative} or bake the material"
                    if alternative
                    else "bake the material"
                )
                issues.append(
                    f"Principled '{name}' is active, but the RealityKit Portable profile "
                    f"does not export it; {remediation}."
                )

    if (
        profile == 'realitykit_pbr2'
        and coat_active
        and 'Coat Tint' not in linked_coat_inputs
        and _active('Coat Tint', (1.0, 1.0, 1.0, 1.0))
    ):
        issues.append(
            "Principled 'Coat Tint' has no RealityKit PBR Surface 2 input; "
            "select OpenPBR 1.1 or bake the material."
        )

    if (
        profile in {'realitykit_pbr2', 'openpbr_1_1'}
        and _active('Specular Tint', (1.0, 1.0, 1.0, 1.0))
    ):
        issues.append(
            "Principled 'Specular Tint' color semantics are not verified against the "
            "selected MaterialX surface; bake the material before export."
        )

    if _active('Sheen Weight') and profile == "realitykit_pbr2":
        roughness = node.inputs.get('Sheen Roughness')
        roughness_is_custom = False
        if roughness is not None:
            if roughness.is_linked:
                roughness_is_custom = True
            else:
                try:
                    roughness_is_custom = abs(float(roughness.default_value) - 0.5) > 1e-6
                except (TypeError, ValueError):
                    pass
        if roughness_is_custom:
            issues.append(
                "Principled 'Sheen Roughness' has no RealityKit PBR Surface 2 input; "
                "bake it or select OpenPBR 1.1."
            )
    return issues


def _effective_texture_mapping_uses(nodes):
    """Collect non-default mappings that the material extractor will author."""

    # Keep the validator importable without OpenUSD/Blender initialization;
    # these helpers are pure until invoked against a real node graph.
    from ..export.materials.extract.core import (
        _extract_mapping_from_node,
        _extract_uv_map_from_node,
    )
    from ..export.materials.mapping import effective_texture_mapping_contract

    contracts = {}
    extraction_errors = []
    image_nodes = sorted(
        (
            node
            for node in nodes
            if getattr(node, "type", "") in {"TEX_IMAGE", "TEX_ENVIRONMENT"}
        ),
        key=lambda node: (str(getattr(node, "name", "")), id(node)),
    )
    for image_node in image_nodes:
        inputs = getattr(image_node, "inputs", None)
        vector_socket = inputs.get("Vector") if inputs is not None else None
        if not vector_socket or not getattr(vector_socket, "is_linked", False):
            continue
        links = list(getattr(vector_socket, "links", []) or [])
        if not links or not getattr(links[0], "from_node", None):
            continue
        source_node = links[0].from_node
        try:
            mapping = _extract_mapping_from_node(source_node)
            uv_map = getattr(image_node, "uv_map", "") or ""
            if not uv_map:
                uv_map = _extract_uv_map_from_node(source_node)
            contract = effective_texture_mapping_contract(mapping, uv_map)
        except ValueError as exc:
            extraction_errors.append((image_node, str(exc)))
            continue
        if contract is not None:
            contracts.setdefault(contract, []).append(image_node)
    return contracts, extraction_errors


def validate_material(
    material,
    only_connected: bool = True,
    strict: bool = False,
    surface_profile: str = "realitykit_portable",
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

    authored_nodes = _collect_used_nodes(material)
    if only_connected:
        used_nodes = authored_nodes
    else:
        used_nodes = set(material.node_tree.nodes)

    def add_issue(
        kind: str,
        node,
        message: str,
        force_error: bool = False,
        removable: bool = True,
    ) -> None:
        target = "errors" if force_error else kind
        _add_issue(result, target, node, message, removable=removable)

    mapping_contracts, mapping_extraction_errors = (
        _effective_texture_mapping_uses(authored_nodes)
    )
    for image_node, message in mapping_extraction_errors:
        add_issue(
            "warnings",
            image_node,
            message,
            force_error=strict,
            removable=False,
        )
    if len(mapping_contracts) > 1:
        mapped_nodes = sorted(
            (node for nodes in mapping_contracts.values() for node in nodes),
            key=lambda node: (str(getattr(node, "name", "")), id(node)),
        )
        add_issue(
            "warnings",
            mapped_nodes[-1],
            (
                f"Material uses {len(mapping_contracts)} distinct non-default texture "
                "mappings, but RealityKit honors only the first 2D texture transform "
                "per material. Use identical Mapping values and one UV set for every "
                "transformed texture, or bake the transforms into the images."
            ),
            force_error=strict,
            removable=False,
        )

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
            if node_type == 'BSDF_PRINCIPLED':
                for issue in _unsupported_principled_inputs(node, surface_profile):
                    add_issue("warnings", node, issue, force_error=strict, removable=False)
            if node_type == 'NORMAL_MAP' and getattr(node, "convention", 'OPENGL') == 'DIRECTX':
                add_issue(
                    "warnings",
                    node,
                    "Normal Map uses the DirectX green channel convention; "
                    "RealityKit expects OpenGL normal maps.",
                    force_error=strict,
                    removable=False,
                )
            if node_type == 'NORMAL_MAP':
                strength_socket = node.inputs.get('Strength') if hasattr(node, 'inputs') else None
                strength_is_linked = bool(
                    strength_socket is not None
                    and getattr(strength_socket, 'is_linked', False)
                )
                if strength_is_linked:
                    add_issue(
                        "warnings",
                        node,
                        "Linked Normal Map Strength requires baking; only a constant strength is mapped.",
                        force_error=strict,
                        removable=False,
                    )
                profile = (surface_profile or 'realitykit_portable').strip().lower()
                if (
                    profile == 'realitykit_pbr2'
                    and strength_socket is not None
                    and not strength_is_linked
                    and _values_differ(
                        getattr(strength_socket, 'default_value', None),
                        1.0,
                    )
                ):
                    add_issue(
                        "warnings",
                        node,
                        "RealityKit PBR Surface 2 cannot safely apply non-default Normal Map "
                        "Strength without double-decoding the normal; bake the normal map.",
                        force_error=strict,
                        removable=False,
                    )
                normal_space = str(getattr(node, 'space', 'TANGENT') or 'TANGENT').upper()
                if profile == 'realitykit_pbr2' and normal_space != 'TANGENT':
                    add_issue(
                        "warnings",
                        node,
                        f"RealityKit PBR Surface 2 cannot safely export {normal_space} Normal Map "
                        "space without double-decoding; bake a tangent-space normal map.",
                        force_error=strict,
                        removable=False,
                    )
            if node_type == 'VALTORGB':
                ramp = getattr(node, "color_ramp", None)
                interpolation = (getattr(ramp, "interpolation", "LINEAR") or "LINEAR").upper()
                color_mode = (getattr(ramp, "color_mode", "RGB") or "RGB").upper()
                if color_mode != "RGB" or interpolation not in {"LINEAR", "CONSTANT", "EASE"}:
                    add_issue(
                        "warnings",
                        node,
                        f"Color Ramp {color_mode}/{interpolation} requires baking; only RGB Linear, "
                        "Constant, and Ease are mapped exactly.",
                        force_error=strict,
                        removable=False,
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
            if _is_supported_mix(node):
                continue
            add_issue(
                "warnings",
                node,
                "Mix node requires baking unless it is a plain mix or multiply/add/subtract "
                "of resolvable linked inputs, or Factor is 0/1 with a passthrough input.",
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
    surface_profile: str = "realitykit_portable",
) -> Dict[str, object]:
    """Validate a collection of materials and aggregate issues."""
    summary = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "materials": [],
    }

    for material in materials:
        result = validate_material(
            material,
            only_connected=only_connected,
            strict=strict,
            surface_profile=surface_profile,
        )
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


def _add_issue(
    result: Dict[str, object],
    kind: str,
    node,
    message: str,
    removable: bool = True,
) -> None:
    entry = {
        "node_name": getattr(node, "name", ""),
        "node_type": getattr(node, "type", ""),
        "message": message,
        "node": node,
    }
    result[kind].append(entry)
    # Socket-level issues on otherwise-supported nodes (e.g. a Principled with
    # Sheen enabled) must not land in offending_nodes: Remove Offenders would
    # delete the whole node over one bad input.
    if kind == "errors" and removable:
        result["offending_nodes"].append(entry)
    elif kind != "errors":
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
    blend = (getattr(node, "blend_type", "") or "MIX").upper()
    if fac_value == 1.0 and blend == 'MIX':
        return bool(b_socket and b_socket.is_linked)
    return False


_RESOLVABLE_MIX_BLENDS = {'MULTIPLY', 'ADD', 'SUBTRACT'}


def _mix_node_params(node):
    blend = (getattr(node, "blend_type", "") or "MIX").upper()
    if not hasattr(node, "inputs"):
        return blend, None, None, None
    fac_socket = node.inputs.get('Fac') or node.inputs.get('Factor')
    fac = None
    if fac_socket and not fac_socket.is_linked:
        try:
            fac = float(fac_socket.default_value)
        except Exception:
            pass
    a_socket = node.inputs.get('Color1') or node.inputs.get('A')
    b_socket = node.inputs.get('Color2') or node.inputs.get('B')
    return blend, fac, a_socket, b_socket


def _is_supported_mix(node) -> bool:
    """Match the exact Mix subset implemented by material extraction."""
    if _is_identity_mix(node):
        return True
    if not node or getattr(node, "type", "") not in {'MIX', 'MIX_RGB'}:
        return False
    blend, fac, a_socket, b_socket = _mix_node_params(node)
    if fac is None:
        return False
    both_linked = bool(
        a_socket and b_socket and a_socket.is_linked and b_socket.is_linked
    )
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
