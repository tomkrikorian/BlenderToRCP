"""
Texture authoring helpers for MaterialX USD graphs.
"""

import math
from typing import Any, Dict, Optional, Tuple

from ..usd_utils import Sdf, UsdShade
from ...manifest.materialx_nodes import (
    select_node_def_for_node,
    select_nodedef_name_for_node,
)
from .conversions import _map_mtlx_type_to_sdf, _create_convert_output
from .helpers import _image_shader_name, _sanitize_name


def _texture_cache_key(texture_spec: Dict[str, Any]) -> Tuple[Any, ...]:
    """Build a stable cache key for shared texture nodes."""
    mapping = texture_spec.get("mapping") or {}
    offset = tuple(mapping.get("offset") or (0.0, 0.0))
    scale = tuple(mapping.get("scale") or (1.0, 1.0))
    rotate = float(mapping.get("rotate") or 0.0)
    pivot = tuple(mapping.get("pivot") or (0.0, 0.0))
    operationorder = mapping.get("operationorder")

    return (
        texture_spec.get("path"),
        texture_spec.get("texcoord"),
        offset,
        scale,
        rotate,
        pivot,
        operationorder,
        texture_spec.get("colorspace"),
        texture_spec.get("alpha_mode"),
        texture_spec.get("type"),
    )


def _coerce_texture_spec_for_input(
    texture_spec: Dict[str, Any],
    input_def: Optional[Dict[str, Any]],
    diagnostics=None,
) -> Dict[str, Any]:
    """Coerce texture output hints to match the expected input type."""
    if not input_def:
        return texture_spec
    type_name = (input_def.get('type') or '').lower()
    if not type_name:
        return texture_spec
    output_type = (texture_spec.get('output_type') or '').lower()
    channel = (texture_spec.get('channel') or '').lower()
    if not output_type:
        return texture_spec

    coerced = dict(texture_spec)
    if type_name in ('color3', 'vector3', 'half3') and output_type in ('color4', 'vector4'):
        coerced['output_type'] = 'color3' if type_name in ('color3', 'half3') else 'vector3'
    elif type_name in ('color4', 'half4') and output_type == 'color3':
        coerced['output_type'] = 'color4'
    elif type_name in ('vector2', 'half2') and output_type in ('vector4',):
        coerced['output_type'] = 'vector2'
    elif type_name in ('float', 'integer', 'half') and output_type in ('color3', 'color4', 'vector3', 'vector4'):
        if not channel:
            coerced['channel'] = 'r'
        coerced['output_type'] = 'float'

    if diagnostics and coerced != texture_spec:
        diagnostics.add_warning(
            f"Coerced texture output '{output_type}' to '{coerced.get('output_type')}' "
            f"for input type '{type_name}'."
        )
    return coerced


def _create_texture_connection(
    stage,
    nodegraph_path: str,
    input_name: str,
    texture_spec: Dict[str, Any],
    manifest: Dict[str, Any],
    material_name: str,
    texture_cache: Optional[Dict[Any, Dict[str, Any]]] = None,
    diagnostics=None,
):
    """Create texture nodes and return the output to connect."""
    texture_path = texture_spec.get('path')
    if not texture_path:
        return None

    output_type = texture_spec.get('output_type', 'color3')
    desired_type = (output_type or 'color3').lower()
    channel = (texture_spec.get('channel') or '').lower()
    texture_kind = texture_spec.get('type') or 'texture'
    node_base = _image_shader_name(stage, nodegraph_path, input_name)

    cache_key = _texture_cache_key(texture_spec)
    if texture_cache is not None:
        cached = texture_cache.get(cache_key)
        if cached:
            texture_output = cached.get("output")
            current_type = cached.get("type") or desired_type
            if texture_output:
                texture_output, current_type = _resolve_texture_output(
                    manifest,
                    stage,
                    nodegraph_path,
                    input_name,
                    texture_output,
                    current_type,
                    desired_type,
                    channel,
                    texture_kind,
                    bool(texture_spec.get("force_separate4")),
                    diagnostics,
                )
                scale = texture_spec.get('scale')
                if scale is not None and texture_output:
                    scaled_output = _create_scale_output(
                        manifest,
                        stage,
                        nodegraph_path,
                        input_name,
                        texture_output,
                        desired_type,
                        scale,
                    )
                    if scaled_output:
                        texture_output = scaled_output
                return texture_output

    rk_texture_def = None
    if rk_texture_def:
        nodedef_name = rk_texture_def.get('nodedef_name')
        node_id = rk_texture_def.get('node_id') or "RealityKitTexture2D"
        output_defs = rk_texture_def.get('outputs') or []
        output_type = (output_defs[0].get('type') if output_defs else None) or "vector4"
        current_type = output_type.lower()
        output_sdf_type = _map_mtlx_type_to_sdf(current_type) or Sdf.ValueTypeNames.Float4
    else:
        image_type = _image_output_hint(desired_type, channel, texture_kind)
        override_type = texture_spec.get("image_type_override")
        if override_type:
            image_type = override_type
        nodedef_name, output_sdf_type = _image_nodedef_for_output(manifest, image_type)
        node_id = _texture_node_id_from_nodedef(nodedef_name)
        current_type = image_type

    if _is_ktx_required(manifest, node_id) and not _is_ktx_path(texture_path):
        if diagnostics:
            diagnostics.add_ktx_required_node(node_id, material_name)
            diagnostics.add_warning(
                f"KTX-required node '{node_id}' used without KTX texture for '{input_name}'."
            )
        return None

    texture_prim = stage.DefinePrim(f"{nodegraph_path}/{node_base}", "Shader")
    texture_shader = UsdShade.Shader(texture_prim)
    texture_shader.CreateIdAttr(nodedef_name)

    file_input = texture_shader.CreateInput("file", Sdf.ValueTypeNames.Asset)
    file_input.Set(texture_path)

    texcoord_name = texture_spec.get('texcoord')
    mapping = texture_spec.get('mapping')
    texcoord_output = None
    if texcoord_name:
        texcoord_output = _create_geomprop_texcoord(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            texcoord_name,
            diagnostics,
        )
    elif mapping:
        texcoord_output = _create_geomprop_texcoord(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            "UV0",
            diagnostics,
        )

    if mapping:
        place2d_output = _create_place2d_node(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            mapping,
            texcoord_output,
            diagnostics,
        )
        if place2d_output:
            texcoord_input = texture_shader.CreateInput("texcoord", Sdf.ValueTypeNames.Float2)
            texcoord_input.ConnectToSource(place2d_output)
    elif texcoord_output:
        texcoord_input = texture_shader.CreateInput("texcoord", Sdf.ValueTypeNames.Float2)
        texcoord_input.ConnectToSource(texcoord_output)

    texture_output = texture_shader.CreateOutput("out", output_sdf_type)

    if texture_cache is not None:
        texture_cache[cache_key] = {"output": texture_output, "type": current_type}

    # Color space is handled by Reality Composer Pro; avoid injecting conversion nodes.

    if texture_kind == 'normal_texture':
        # Blender's Normal Map node corresponds to ShaderGraph/MaterialX `normalmap`
        # (transforms tangent/object-space normal vectors into world space).
        if current_type != 'vector3':
            texture_output = _create_convert_output(
                manifest,
                stage,
                nodegraph_path,
                input_name,
                texture_output,
                current_type,
                'vector3',
                diagnostics,
            )
            current_type = 'vector3'

        normalmap_nodedef = select_nodedef_name_for_node(
            manifest,
            "normalmap",
            output_type="vector3",
        ) or "ND_normalmap"

        normalmap_name = _sanitize_name(f"NormalMap_{input_name}")
        normalmap_prim = stage.DefinePrim(f"{nodegraph_path}/{normalmap_name}", "Shader")
        normalmap_shader = UsdShade.Shader(normalmap_prim)
        normalmap_shader.CreateIdAttr(normalmap_nodedef)

        in_input = normalmap_shader.CreateInput("in", Sdf.ValueTypeNames.Float3)
        in_input.ConnectToSource(texture_output)

        # Optional strength hook (defaults to 1.0 if omitted).
        strength = texture_spec.get("scale")
        if strength is not None:
            try:
                strength_value = float(strength)
            except Exception:
                strength_value = None
            if strength_value is not None and abs(strength_value - 1.0) > 1e-6:
                normalmap_shader.CreateInput("scale", Sdf.ValueTypeNames.Float).Set(strength_value)

        # Optional space override (defaults to tangent).
        space = (texture_spec.get("space") or "").strip().lower()
        if space in {"tangent", "object"}:
            normalmap_shader.CreateInput("space", Sdf.ValueTypeNames.String).Set(space)

        return normalmap_shader.CreateOutput("out", Sdf.ValueTypeNames.Float3)

    texture_output, current_type = _resolve_texture_output(
        manifest,
        stage,
        nodegraph_path,
        input_name,
        texture_output,
        current_type,
        desired_type,
        channel,
        texture_kind,
        bool(texture_spec.get("force_separate4")),
        diagnostics,
    )

    scale = texture_spec.get('scale')
    if scale is not None and texture_output:
        scaled_output = _create_scale_output(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            texture_output,
            desired_type,
            scale,
        )
        if scaled_output:
            texture_output = scaled_output

    return texture_output


def _texture_node_id_from_nodedef(nodedef_name: str) -> str:
    """Convert a nodedef name to a node id (strip ND_ and type suffix)."""
    if nodedef_name.startswith("ND_"):
        base = nodedef_name[3:]
    else:
        base = nodedef_name

    for suffix in ("_color3", "_color4", "_vector2", "_vector3", "_vector4", "_float"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def _create_geomprop_texcoord(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    texcoord_name: str,
    diagnostics=None,
):
    """Create a texcoord or geompropvalue node for texture coordinates."""
    texcoord_name = (texcoord_name or "").strip() or "UV0"
    if texcoord_name.upper() == "UV0":
        texcoord_nodedef = select_nodedef_name_for_node(
            manifest,
            "texcoord",
            output_type="vector2",
        )
        if not texcoord_nodedef:
            if diagnostics:
                diagnostics.add_warning("No texcoord nodedef found for default UVs.")
                diagnostics.add_error("No texcoord nodedef found for default UVs.")
            return None
        texcoord_node_name = _sanitize_name("TextureCoordinates")
        texcoord_path = f"{nodegraph_path}/{texcoord_node_name}"
        existing = stage.GetPrimAtPath(texcoord_path)
        if existing and existing.IsValid():
            existing_shader = UsdShade.Shader(existing)
            output = existing_shader.GetOutput("out")
            return output or existing_shader.CreateOutput("out", Sdf.ValueTypeNames.Float2)
        texcoord_prim = stage.DefinePrim(texcoord_path, "Shader")
        texcoord_shader = UsdShade.Shader(texcoord_prim)
        texcoord_shader.CreateIdAttr(texcoord_nodedef)
        return texcoord_shader.CreateOutput("out", Sdf.ValueTypeNames.Float2)

    texcoord_nodedef = select_nodedef_name_for_node(
        manifest,
        "geompropvalue",
        output_type="vector2",
    )
    if not texcoord_nodedef:
        if diagnostics:
            diagnostics.add_warning(
                f"No geompropvalue nodedef found for texcoord '{texcoord_name}'"
            )
            diagnostics.add_error(
                f"No geompropvalue nodedef found for texcoord '{texcoord_name}'"
            )
        return None

    texcoord_node_name = _sanitize_name(f"texcoord_{texcoord_name}")
    texcoord_path = f"{nodegraph_path}/{texcoord_node_name}"
    existing = stage.GetPrimAtPath(texcoord_path)
    if existing and existing.IsValid():
        existing_shader = UsdShade.Shader(existing)
        output = existing_shader.GetOutput("out")
        return output or existing_shader.CreateOutput("out", Sdf.ValueTypeNames.Float2)
    texcoord_prim = stage.DefinePrim(texcoord_path, "Shader")
    texcoord_shader = UsdShade.Shader(texcoord_prim)
    texcoord_shader.CreateIdAttr(texcoord_nodedef)

    geomprop_input = texcoord_shader.CreateInput("geomprop", Sdf.ValueTypeNames.String)
    geomprop_input.Set(texcoord_name)
    return texcoord_shader.CreateOutput("out", Sdf.ValueTypeNames.Float2)


def _create_place2d_node(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    mapping: Dict[str, Any],
    texcoord_output,
    diagnostics=None,
):
    """Create a place2d node to apply mapping transforms."""
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "place2d",
        output_type="vector2",
    )
    if not nodedef_name:
        if diagnostics:
            diagnostics.add_warning("No place2d nodedef found for UV mapping transforms.")
            diagnostics.add_error("No place2d nodedef found for UV mapping transforms.")
        return None

    node_name = _sanitize_name(f"place2d_{input_name}")
    place_prim = stage.DefinePrim(f"{nodegraph_path}/{node_name}", "Shader")
    place_shader = UsdShade.Shader(place_prim)
    place_shader.CreateIdAttr(nodedef_name)

    if texcoord_output:
        texcoord_input = place_shader.CreateInput("texcoord", Sdf.ValueTypeNames.Float2)
        texcoord_input.ConnectToSource(texcoord_output)

    offset = mapping.get('offset') or (0.0, 0.0)
    scale = mapping.get('scale') or (1.0, 1.0)
    pivot = mapping.get('pivot') or (0.0, 0.0)
    rotate = mapping.get('rotate') or 0.0
    rotate_degrees = math.degrees(rotate)
    operationorder = mapping.get('operationorder')

    place_shader.CreateInput("offset", Sdf.ValueTypeNames.Float2).Set(offset)
    place_shader.CreateInput("scale", Sdf.ValueTypeNames.Float2).Set(scale)
    place_shader.CreateInput("pivot", Sdf.ValueTypeNames.Float2).Set(pivot)
    place_shader.CreateInput("rotate", Sdf.ValueTypeNames.Float).Set(rotate_degrees)
    if operationorder is not None:
        place_shader.CreateInput("operationorder", Sdf.ValueTypeNames.Int).Set(int(operationorder))

    return place_shader.CreateOutput("out", Sdf.ValueTypeNames.Float2)


def _apply_srgb_to_linear(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    source_output,
    output_type: str,
):
    """Apply an approximate sRGB-to-linear conversion using a power node."""
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "power",
        output_type=output_type,
    )
    if not nodedef_name:
        return None

    const_name = _sanitize_name(f"srgb_exp_{input_name}")
    const_prim = stage.DefinePrim(f"{nodegraph_path}/{const_name}", "Shader")
    const_shader = UsdShade.Shader(const_prim)
    const_shader.CreateIdAttr(select_nodedef_name_for_node(manifest, "constant", output_type=output_type))

    exponent = 2.2
    if output_type == 'color4':
        value = (exponent, exponent, exponent, exponent)
    else:
        value = (exponent, exponent, exponent)
    const_shader.CreateInput("value", _map_mtlx_type_to_sdf(output_type)).Set(value)
    const_output = const_shader.CreateOutput("out", _map_mtlx_type_to_sdf(output_type))

    pow_name = _sanitize_name(f"srgb_to_linear_{input_name}")
    pow_prim = stage.DefinePrim(f"{nodegraph_path}/{pow_name}", "Shader")
    pow_shader = UsdShade.Shader(pow_prim)
    pow_shader.CreateIdAttr(nodedef_name)

    pow_in1 = pow_shader.CreateInput("in1", _map_mtlx_type_to_sdf(output_type))
    pow_in1.ConnectToSource(source_output)
    pow_in2 = pow_shader.CreateInput("in2", _map_mtlx_type_to_sdf(output_type))
    pow_in2.ConnectToSource(const_output)
    return pow_shader.CreateOutput("out", _map_mtlx_type_to_sdf(output_type))


def _create_scale_output(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    source_output,
    output_type: str,
    scale: float,
):
    """Multiply a texture output by a scalar scale factor."""
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "multiply",
        output_type=output_type,
    )
    if not nodedef_name:
        return None

    const_name = _sanitize_name(f"scale_{input_name}")
    const_prim = stage.DefinePrim(f"{nodegraph_path}/{const_name}", "Shader")
    const_shader = UsdShade.Shader(const_prim)
    const_shader.CreateIdAttr(select_nodedef_name_for_node(manifest, "constant", output_type=output_type))

    if output_type == 'color4':
        value = (scale, scale, scale, scale)
    elif output_type == 'color3':
        value = (scale, scale, scale)
    elif output_type == 'vector2':
        value = (scale, scale)
    elif output_type == 'vector3':
        value = (scale, scale, scale)
    elif output_type == 'vector4':
        value = (scale, scale, scale, scale)
    else:
        value = float(scale)

    const_shader.CreateInput("value", _map_mtlx_type_to_sdf(output_type)).Set(value)
    const_output = const_shader.CreateOutput("out", _map_mtlx_type_to_sdf(output_type))

    mult_name = _sanitize_name(f"scale_mult_{input_name}")
    mult_prim = stage.DefinePrim(f"{nodegraph_path}/{mult_name}", "Shader")
    mult_shader = UsdShade.Shader(mult_prim)
    mult_shader.CreateIdAttr(nodedef_name)

    mult_in1 = mult_shader.CreateInput("in1", _map_mtlx_type_to_sdf(output_type))
    mult_in1.ConnectToSource(source_output)
    mult_in2 = mult_shader.CreateInput("in2", _map_mtlx_type_to_sdf(output_type))
    mult_in2.ConnectToSource(const_output)
    return mult_shader.CreateOutput("out", _map_mtlx_type_to_sdf(output_type))


def _image_nodedef_for_output(manifest: Dict[str, Any], output_type: str) -> Tuple[str, Any]:
    """Pick MaterialX image nodedef and output type from requested output."""
    output_type = (output_type or '').lower()
    color4_type = getattr(Sdf.ValueTypeNames, "Color4f", Sdf.ValueTypeNames.Float4)
    mapping = {
        'float': ("ND_image_float", Sdf.ValueTypeNames.Float),
        'color3': ("ND_image_color3", Sdf.ValueTypeNames.Color3f),
        'color4': ("ND_image_color4", color4_type),
        'vector2': ("ND_image_vector2", Sdf.ValueTypeNames.Float2),
        'vector3': ("ND_image_vector3", Sdf.ValueTypeNames.Float3),
        'vector4': ("ND_image_vector4", Sdf.ValueTypeNames.Float4),
    }
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "image",
        output_type=output_type,
    )
    if nodedef_name:
        # If found via manifest, infer output type from the nodedef.
        node_def = manifest.get("nodes", {}).get(nodedef_name)
        if node_def and node_def.get("outputs"):
            out_type = (node_def["outputs"][0].get("type") or "").lower()
            return nodedef_name, _map_mtlx_type_to_sdf(out_type) or mapping.get(output_type, (None, None))[1]
        return nodedef_name, mapping.get(output_type, ("ND_image_color3", Sdf.ValueTypeNames.Color3f))[1]
    return mapping.get(output_type, ("ND_image_color3", Sdf.ValueTypeNames.Color3f))


def _image_output_hint(output_type: str, channel: str, texture_kind: Optional[str]) -> str:
    """Choose a safe image output type for the requested connection."""
    output_type = (output_type or '').lower()
    channel = (channel or '').lower()
    if output_type in ('color4', 'vector4'):
        return 'color4'
    if output_type == 'float' and channel == 'a':
        return 'color4'
    # Normal maps must be treated as raw vectors (avoid color-space assumptions).
    if texture_kind == 'normal_texture':
        return 'vector3'
    if output_type in ('vector3', 'vector2'):
        return 'color3'
    if output_type == 'float' and channel:
        return 'color3'
    if output_type == 'float':
        return 'color3'
    return 'color3'


def _resolve_texture_output(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    texture_output,
    current_type: str,
    desired_type: str,
    channel: str,
    texture_kind: str,
    force_separate4: bool,
    diagnostics=None,
):
    """Resolve texture output conversions including RGBA separation."""
    if not texture_output:
        return None, current_type

    current_type = (current_type or '').lower()
    desired_type = (desired_type or '').lower()
    channel = (channel or '').lower()

    if desired_type == 'float' and not channel:
        channel = 'r'
        if diagnostics:
            diagnostics.add_warning(
                f"Texture '{input_name}' connected to float input without a channel; "
                "defaulting to 'r'."
            )

    if texture_kind != 'normal_texture' and current_type == 'color4':
        base_name = texture_output.GetPrim().GetName() if texture_output.GetPrim() else input_name
        base_name = _sanitize_name(base_name or input_name)
        if channel and channel not in ('rgb', 'rgba'):
            separated = _create_separate4_outputs(
                manifest,
                stage,
                nodegraph_path,
                base_name,
                texture_output,
                diagnostics,
            )
            channel_output = _channel_from_separate(separated, channel)
            if channel_output:
                texture_output = channel_output
                current_type = 'float'
                channel = ''
        elif desired_type in ('color3', 'vector3') and force_separate4:
            separated = _create_separate4_outputs(
                manifest,
                stage,
                nodegraph_path,
                base_name,
                texture_output,
                diagnostics,
            )
            color_output = _create_combine3_output(
                manifest,
                stage,
                nodegraph_path,
                base_name,
                separated,
                diagnostics,
            )
            if color_output:
                texture_output = color_output
                current_type = 'color3'

    if channel and channel not in ('rgb', 'rgba'):
        swizzle_output = _create_swizzle_output(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            texture_output,
            channel,
            desired_type,
            diagnostics,
        )
        if swizzle_output:
            texture_output = swizzle_output
            current_type = 'float'

    if current_type != desired_type:
        texture_output = _create_convert_output(
            manifest,
            stage,
            nodegraph_path,
            input_name,
            texture_output,
            current_type,
            desired_type,
            diagnostics,
        )
        current_type = desired_type

    return texture_output, current_type


def _create_separate4_outputs(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    base_name: str,
    source_output,
    diagnostics=None,
):
    """Create or reuse a separate4 node and return its outputs."""
    if not source_output:
        return None
    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "separate4",
        input_type="color4",
    )
    if not nodedef_name:
        if diagnostics:
            diagnostics.add_warning("No separate4 nodedef found for color4 inputs.")
            diagnostics.add_error("No separate4 nodedef found for color4 inputs.")
        return None

    node_name = _sanitize_name(f"{base_name}_separate4")
    node_path = f"{nodegraph_path}/{node_name}"
    existing = stage.GetPrimAtPath(node_path)
    if existing and existing.IsValid():
        shader = UsdShade.Shader(existing)
    else:
        prim = stage.DefinePrim(node_path, "Shader")
        shader = UsdShade.Shader(prim)
        shader.CreateIdAttr(nodedef_name)
        in_input = shader.CreateInput("in", source_output.GetTypeName())
        in_input.ConnectToSource(source_output)

    outputs = {
        "r": shader.GetOutput("outr") or shader.CreateOutput("outr", Sdf.ValueTypeNames.Float),
        "g": shader.GetOutput("outg") or shader.CreateOutput("outg", Sdf.ValueTypeNames.Float),
        "b": shader.GetOutput("outb") or shader.CreateOutput("outb", Sdf.ValueTypeNames.Float),
        "a": shader.GetOutput("outa") or shader.CreateOutput("outa", Sdf.ValueTypeNames.Float),
    }
    return outputs


def _create_combine3_output(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    base_name: str,
    separated_outputs: Optional[Dict[str, Any]],
    diagnostics=None,
):
    """Create a combine3 node from separated outputs."""
    if not separated_outputs:
        return None

    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "combine3",
        output_type="color3",
    )
    if not nodedef_name:
        if diagnostics:
            diagnostics.add_warning("No combine3 nodedef found for color3 outputs.")
            diagnostics.add_error("No combine3 nodedef found for color3 outputs.")
        return None

    node_name = _sanitize_name(f"{base_name}_combine3")
    node_path = f"{nodegraph_path}/{node_name}"
    existing = stage.GetPrimAtPath(node_path)
    if existing and existing.IsValid():
        shader = UsdShade.Shader(existing)
    else:
        prim = stage.DefinePrim(node_path, "Shader")
        shader = UsdShade.Shader(prim)
        shader.CreateIdAttr(nodedef_name)

    in1 = shader.CreateInput("in1", Sdf.ValueTypeNames.Float)
    in2 = shader.CreateInput("in2", Sdf.ValueTypeNames.Float)
    in3 = shader.CreateInput("in3", Sdf.ValueTypeNames.Float)
    if separated_outputs.get("r"):
        in1.ConnectToSource(separated_outputs["r"])
    if separated_outputs.get("g"):
        in2.ConnectToSource(separated_outputs["g"])
    if separated_outputs.get("b"):
        in3.ConnectToSource(separated_outputs["b"])

    return shader.GetOutput("out") or shader.CreateOutput("out", Sdf.ValueTypeNames.Color3f)


def _channel_from_separate(separated_outputs: Optional[Dict[str, Any]], channel: str):
    """Return the output matching the requested channel from a separate4 node."""
    if not separated_outputs or not channel:
        return None
    channel = channel.lower()
    mapping = {
        "r": "r",
        "g": "g",
        "b": "b",
        "a": "a",
        "x": "r",
        "y": "g",
        "z": "b",
        "w": "a",
    }
    key = mapping.get(channel)
    if not key:
        return None
    return separated_outputs.get(key)


def _is_ktx_required(manifest: Dict[str, Any], node_id: str) -> bool:
    """Check if a nodedef is flagged as KTX-required in the manifest."""
    node_def = select_node_def_for_node(manifest, node_id)
    if not node_def:
        return False
    return bool(node_def.get('policy', {}).get('requires_ktx'))


def _is_ktx_path(texture_path: str) -> bool:
    """Return True if the texture path uses a KTX extension."""
    return texture_path.lower().endswith((".ktx", ".ktx2"))


def _create_swizzle_output(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    texture_output,
    channel: str,
    output_type: str,
    diagnostics=None,
):
    """Create a swizzle node to extract a single channel as float."""
    if channel not in ('r', 'g', 'b', 'a', 'x', 'y', 'z', 'w'):
        if diagnostics:
            diagnostics.add_warning(
                f"Unsupported texture channel '{channel}' for input '{input_name}'."
            )
            diagnostics.add_error(
                f"Unsupported texture channel '{channel}' for input '{input_name}'."
            )
        return None

    input_sdf_type = texture_output.GetTypeName()
    swizzle_nodedef = _swizzle_nodedef_for_input(
        manifest,
        output_type,
        channel,
        input_sdf_type,
    )
    if not swizzle_nodedef:
        if diagnostics:
            diagnostics.add_warning(
                f"No swizzle nodedef for type '{output_type}' on input '{input_name}'."
            )
            diagnostics.add_error(
                f"No swizzle nodedef for type '{output_type}' on input '{input_name}'."
            )
        return None

    swizzle_name = _sanitize_name(f"swizzle_{input_name}_{channel}")
    swizzle_prim = stage.DefinePrim(f"{nodegraph_path}/{swizzle_name}", "Shader")
    swizzle_shader = UsdShade.Shader(swizzle_prim)
    swizzle_shader.CreateIdAttr(swizzle_nodedef)

    in_input = swizzle_shader.CreateInput("in", input_sdf_type)
    in_input.ConnectToSource(texture_output)

    channels_input = swizzle_shader.CreateInput("channels", Sdf.ValueTypeNames.String)
    channels_input.Set(channel)

    if diagnostics:
        diagnostics.add_warning(
            f"Inserted swizzle node '{swizzle_nodedef}' for {input_name}: channel '{channel}'."
        )

    return swizzle_shader.CreateOutput("out", Sdf.ValueTypeNames.Float)


def _swizzle_nodedef_for_input(
    manifest: Dict[str, Any],
    output_type: str,
    channel: str,
    input_sdf_type,
):
    """Pick a MaterialX swizzle nodedef based on output hint and input type."""
    output_type = (output_type or '').lower()
    channel = (channel or '').lower()

    input_type = None
    if input_sdf_type == Sdf.ValueTypeNames.Color3f:
        input_type = "color3"
    else:
        color4_type = getattr(Sdf.ValueTypeNames, "Color4f", None)
        if color4_type and input_sdf_type == color4_type:
            input_type = "color4"
        elif input_sdf_type == Sdf.ValueTypeNames.Float2:
            input_type = "vector2"
        elif input_sdf_type == Sdf.ValueTypeNames.Float3:
            input_type = "vector3"
        elif input_sdf_type == Sdf.ValueTypeNames.Float4:
            input_type = "vector4"

    if input_type and output_type == "float":
        explicit = f"ND_swizzle_{input_type}_float"
        if explicit in manifest.get("nodes", {}):
            return explicit
        signature = f"in[in:{input_type},channels:string]|out[out:float]"
        nodedef = select_nodedef_name_for_node(
            manifest,
            "swizzle",
            signature=signature,
            output_type="float",
        )
        if nodedef:
            return nodedef

    if output_type in ('color3',):
        return "ND_swizzle_color3_float"
    if output_type in ('color4', 'float'):
        if output_type == 'float' and channel in ('r', 'g', 'b'):
            return "ND_swizzle_color3_float"
        return "ND_swizzle_color4_float"
    if output_type in ('vector2',):
        return "ND_swizzle_vector2_float"
    if output_type in ('vector3',):
        return "ND_swizzle_vector3_float"
    if output_type in ('vector4',):
        return "ND_swizzle_vector4_float"

    if input_sdf_type == Sdf.ValueTypeNames.Color3f:
        return "ND_swizzle_color3_float"
    color4_type = getattr(Sdf.ValueTypeNames, "Color4f", None)
    if color4_type and input_sdf_type == color4_type:
        return "ND_swizzle_color4_float"
    if input_sdf_type == Sdf.ValueTypeNames.Float2:
        return "ND_swizzle_vector2_float"
    if input_sdf_type == Sdf.ValueTypeNames.Float3:
        return "ND_swizzle_vector3_float"
    if input_sdf_type == Sdf.ValueTypeNames.Float4:
        return "ND_swizzle_vector4_float"
    return None
