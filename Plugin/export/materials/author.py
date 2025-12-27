"""
MaterialX material authoring for USD stages.
"""

from typing import Any, Dict

from ..usd_utils import UsdShade, Sdf
from .conversions import (
    get_usd_type,
    _map_mtlx_type_to_sdf,
    _normalize_mtlx_type,
    _sdf_type_to_mtlx,
    _set_shader_input_value,
    _default_value_from_input_def,
    _coerce_value_to_input_type,
    _create_convert_output,
)
from .helpers import (
    _assign_graph_node_names,
    _collect_connected_inputs,
    _get_node_def,
    _get_nodedef_name,
    _get_input_def,
    _get_output_def,
)
from .textures import (
    _coerce_texture_spec_for_input,
    _create_texture_connection,
    _texture_cache_key,
)


def create_materialx_material(
    stage,
    material_path: str,
    material_name: str,
    graph: Dict[str, Any],
    manifest: Dict[str, Any],
    diagnostics=None,
):
    """Create a MaterialX material in USD stage."""
    material_prim = stage.DefinePrim(material_path, "Material")
    material = UsdShade.Material(material_prim)
    nodes = graph.get('nodes', [])
    if not nodes:
        raise ValueError("MaterialX graph has no nodes")

    connections = graph.get('connections', [])
    name_map = _assign_graph_node_names(stage, material_path, nodes)
    connected_inputs = _collect_connected_inputs(connections)

    texture_prefs: Dict[Any, str] = {}
    texture_alpha_usage: Dict[Any, bool] = {}
    for node in nodes:
        for input_value in node.get('inputs', {}).values():
            if not isinstance(input_value, dict):
                continue
            if input_value.get("type") != "texture":
                continue
            key = _texture_cache_key(input_value)
            channel = (input_value.get("channel") or "").lower()
            output_type = (input_value.get("output_type") or "").lower()
            if channel == "a":
                texture_prefs[key] = "color4"
                texture_alpha_usage[key] = True
            elif output_type in {"color4", "vector4"}:
                texture_prefs[key] = "color4"

    texture_cache: Dict[Any, Dict[str, Any]] = {}

    node_shaders: Dict[str, Any] = {}
    node_defs: Dict[str, Any] = {}

    for node in nodes:
        node_name = node.get('name')
        node_id = node.get('node_id')
        if not node_name or not node_id:
            continue
        node_def = _get_node_def(manifest, node_id)
        shader_nodedef = _get_nodedef_name(node_id, node_def)
        if diagnostics and not node_def:
            diagnostics.add_warning(
                f"Missing nodedef for node '{node_id}' in material '{material_name}'."
            )
            diagnostics.add_error(
                f"Missing nodedef for node '{node_id}' in material '{material_name}'."
            )

        shader_path = f"{material_path}/{name_map.get(node_name, node_name)}"
        shader_prim = stage.DefinePrim(shader_path, "Shader")
        shader = UsdShade.Shader(shader_prim)

        shader.CreateIdAttr(shader_nodedef)
        if hasattr(shader, "SetSourceType"):
            shader.SetSourceType("mtlx")

        node_shaders[node_name] = shader
        node_defs[node_name] = node_def

        for input_name, input_value in node.get('inputs', {}).items():
            if input_name in connected_inputs.get(node_name, set()):
                continue
            input_def = _get_input_def(node_def, input_name)
            input_type = _map_mtlx_type_to_sdf(input_def.get('type') if input_def else None)
            if diagnostics and input_def is None:
                diagnostics.add_warning(
                    f"Missing input definition '{input_name}' for node '{node_id}' in material '{material_name}'."
                )
                diagnostics.add_error(
                    f"Missing input definition '{input_name}' for node '{node_id}' in material '{material_name}'."
                )

            if isinstance(input_value, dict):
                if input_def:
                    input_value = _coerce_texture_spec_for_input(input_value, input_def, diagnostics)
                cache_key = _texture_cache_key(input_value)
                pref_type = texture_prefs.get(cache_key)
                if pref_type:
                    input_value = dict(input_value)
                    input_value["image_type_override"] = pref_type
                if texture_alpha_usage.get(cache_key):
                    input_value = dict(input_value)
                    input_value["force_separate4"] = True
                texture_output = _create_texture_connection(
                    stage,
                    material_path,
                    input_name,
                    input_value,
                    manifest,
                    material_name,
                    texture_cache,
                    diagnostics
                )
                if texture_output:
                    shader_input = shader.CreateInput(
                        input_name,
                        input_type or texture_output.GetTypeName()
                    )
                    shader_input.ConnectToSource(texture_output)
                else:
                    default_value = _default_value_from_input_def(input_def)
                    if default_value is not None:
                        shader_input = shader.CreateInput(
                            input_name,
                            input_type or get_usd_type(default_value)
                        )
                        coerced_value = _coerce_value_to_input_type(default_value, input_def)
                        _set_shader_input_value(shader_input, coerced_value)
            else:
                shader_input = shader.CreateInput(input_name, input_type or get_usd_type(input_value))
                coerced_value = _coerce_value_to_input_type(input_value, input_def)
                _set_shader_input_value(shader_input, coerced_value)

    for connection in connections:
        from_node = connection.get("from_node")
        to_node = connection.get("to_node")
        if not from_node or not to_node:
            continue
        from_shader = node_shaders.get(from_node)
        to_shader = node_shaders.get(to_node)
        if not from_shader or not to_shader:
            continue

        output_name = connection.get("from_output") or "out"
        input_name = connection.get("to_input")
        if not input_name:
            continue

        from_def = node_defs.get(from_node)
        to_def = node_defs.get(to_node)

        output_def = _get_output_def(from_def, output_name)
        output_type = _map_mtlx_type_to_sdf(output_def.get('type') if output_def else None)
        if not output_type:
            output_type = Sdf.ValueTypeNames.Token
            if diagnostics:
                diagnostics.add_warning(
                    f"Unknown output type for '{from_node}.{output_name}' in material '{material_name}'."
                )
                diagnostics.add_error(
                    f"Unknown output type for '{from_node}.{output_name}' in material '{material_name}'."
                )

        shader_output = from_shader.GetOutput(output_name)
        if not shader_output:
            shader_output = from_shader.CreateOutput(output_name, output_type)

        input_def = _get_input_def(to_def, input_name)
        input_type = _map_mtlx_type_to_sdf(input_def.get('type') if input_def else None)
        if not input_type:
            input_type = shader_output.GetTypeName()
            if diagnostics:
                diagnostics.add_warning(
                    f"Unknown input type for '{to_node}.{input_name}' in material '{material_name}'."
                )
                diagnostics.add_error(
                    f"Unknown input type for '{to_node}.{input_name}' in material '{material_name}'."
                )

        shader_input = to_shader.GetInput(input_name)
        if not shader_input:
            shader_input = to_shader.CreateInput(input_name, input_type)

        from_type = _normalize_mtlx_type(output_def.get('type') if output_def else None)
        if not from_type:
            from_type = _normalize_mtlx_type(_sdf_type_to_mtlx(shader_output.GetTypeName()))
        to_type = _normalize_mtlx_type(input_def.get('type') if input_def else None)
        if not to_type:
            to_type = _normalize_mtlx_type(_sdf_type_to_mtlx(input_type))

        if from_type and to_type and from_type != to_type:
            converted_output = _create_convert_output(
                manifest,
                stage,
                material_path,
                input_name,
                shader_output,
                from_type,
                to_type,
                diagnostics,
            )
            shader_input.ConnectToSource(converted_output)
        else:
            shader_input.ConnectToSource(shader_output)

    output_target = graph.get('output')
    if isinstance(output_target, dict):
        output_node_name = output_target.get('node')
        output_name = output_target.get('output') or "out"
    else:
        output_node_name = output_target
        output_name = "out"

    output_node = node_shaders.get(output_node_name)
    if not output_node:
        raise ValueError(f"MaterialX graph output node not found: {output_node_name}")

    output_def = _get_output_def(node_defs.get(output_node_name), output_name)
    output_type = _map_mtlx_type_to_sdf(output_def.get('type') if output_def else None)
    if not output_type:
        output_type = Sdf.ValueTypeNames.Token

    material_output = material.CreateSurfaceOutput("mtlx")
    shader_output = output_node.GetOutput(output_name)
    if not shader_output:
        shader_output = output_node.CreateOutput(output_name, output_type)
    material_output.ConnectToSource(shader_output)

    return material
