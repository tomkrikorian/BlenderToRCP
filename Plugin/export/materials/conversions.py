"""
MaterialX/USD type conversions and conversion-node helpers.
"""

from typing import Any, Dict, Optional

from ..usd_utils import Sdf, Gf, UsdShade, Vt
from ...manifest.materialx_nodes import select_nodedef_name_for_node
from .helpers import _convert_shader_name


def get_usd_type(value: Any):
    """Get USD type from Python value."""
    if isinstance(value, bool):
        return Sdf.ValueTypeNames.Bool
    if isinstance(value, int):
        return Sdf.ValueTypeNames.Int
    if isinstance(value, float):
        return Sdf.ValueTypeNames.Float
    if isinstance(value, list):
        if len(value) == 2:
            return Sdf.ValueTypeNames.Float2
        if len(value) == 3:
            return Sdf.ValueTypeNames.Float3
        if len(value) == 4:
            return Sdf.ValueTypeNames.Float4
    return Sdf.ValueTypeNames.Token


def _map_mtlx_type_to_sdf(type_name: Optional[str]):
    """Map MaterialX type strings to Sdf value types."""
    if not type_name:
        return None

    color4_type = getattr(Sdf.ValueTypeNames, "Color4f", Sdf.ValueTypeNames.Float4)
    mapping = {
        'boolean': Sdf.ValueTypeNames.Bool,
        'integer': Sdf.ValueTypeNames.Int,
        'float': Sdf.ValueTypeNames.Float,
        'half': Sdf.ValueTypeNames.Float,
        'color3': Sdf.ValueTypeNames.Color3f,
        'color4': color4_type,
        'vector2': Sdf.ValueTypeNames.Float2,
        'vector3': Sdf.ValueTypeNames.Float3,
        'vector4': Sdf.ValueTypeNames.Float4,
        'half2': Sdf.ValueTypeNames.Float2,
        'half3': Sdf.ValueTypeNames.Color3f,
        'half4': color4_type,
        'vector2array': Sdf.ValueTypeNames.Float2Array,
        'vector3array': Sdf.ValueTypeNames.Float3Array,
        'string': Sdf.ValueTypeNames.String,
        'filename': Sdf.ValueTypeNames.Asset,
        'surfaceshader': Sdf.ValueTypeNames.Token,
        'displacementshader': Sdf.ValueTypeNames.Token,
        'volumeshader': Sdf.ValueTypeNames.Token,
        'material': Sdf.ValueTypeNames.Token,
    }
    return mapping.get(type_name)


def _normalize_mtlx_type(type_name: Optional[str]) -> Optional[str]:
    """Normalize MaterialX types for conversion nodes."""
    if not type_name:
        return None
    type_name = type_name.lower()
    if type_name in ('half',):
        return 'float'
    if type_name in ('half2',):
        return 'vector2'
    if type_name in ('half3',):
        return 'color3'
    if type_name in ('half4',):
        return 'color4'
    if type_name in ('integer', 'int'):
        return 'integer'
    return type_name


def _sdf_type_to_mtlx(sdf_type):
    """Map Sdf value types back to MaterialX type strings."""
    color4_type = getattr(Sdf.ValueTypeNames, "Color4f", None)
    if sdf_type == Sdf.ValueTypeNames.Float:
        return 'float'
    if sdf_type == Sdf.ValueTypeNames.Int:
        return 'integer'
    if sdf_type == Sdf.ValueTypeNames.Bool:
        return 'boolean'
    if sdf_type == Sdf.ValueTypeNames.Color3f:
        return 'color3'
    if color4_type and sdf_type == color4_type:
        return 'color4'
    if sdf_type == Sdf.ValueTypeNames.Float2:
        return 'vector2'
    if sdf_type == Sdf.ValueTypeNames.Float3:
        return 'vector3'
    if sdf_type == Sdf.ValueTypeNames.Float4:
        return 'vector4'
    return None


def _set_shader_input_value(shader_input, value: Any) -> None:
    """Set a shader input value with basic type coercion."""
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], (list, tuple)):
            if Vt is not None:
                if len(value[0]) == 2:
                    shader_input.Set(Vt.Vec2fArray(value))
                    return
                if len(value[0]) == 3:
                    shader_input.Set(Vt.Vec3fArray(value))
                    return
            shader_input.Set(value)
            return
        if len(value) == 2:
            shader_input.Set(Gf.Vec2f(*value))
        elif len(value) == 3:
            shader_input.Set(Gf.Vec3f(*value))
        elif len(value) == 4:
            shader_input.Set(Gf.Vec4f(*value))
        else:
            shader_input.Set(value)
    else:
        shader_input.Set(value)


def _default_value_from_input_def(input_def: Optional[Dict[str, Any]]):
    """Parse a default value from a MaterialX input definition."""
    if not input_def:
        return None

    value = input_def.get('value')
    if value in (None, ""):
        return None

    type_name = (input_def.get('type') or '').lower()

    if type_name in ('boolean',):
        return str(value).lower() in ('true', '1')
    if type_name in ('integer',):
        try:
            return int(value)
        except ValueError:
            return None
    if type_name in ('float', 'half'):
        try:
            return float(value)
        except ValueError:
            return None
    if type_name in ('color3', 'color4', 'vector2', 'vector3', 'vector4', 'half2', 'half3', 'half4'):
        parts = [p.strip() for p in str(value).split(',') if p.strip() != ""]
        try:
            return [float(p) for p in parts]
        except ValueError:
            return None
    if type_name in ('string', 'filename'):
        return str(value)

    if ',' in str(value):
        parts = [p.strip() for p in str(value).split(',') if p.strip() != ""]
        try:
            return [float(p) for p in parts]
        except ValueError:
            return None

    try:
        return float(value)
    except ValueError:
        return str(value)


def _coerce_value_to_input_type(value: Any, input_def: Optional[Dict[str, Any]]):
    """Coerce list values to match MaterialX input types when possible."""
    if not input_def:
        return value

    type_name = (input_def.get('type') or '').lower()
    if not isinstance(value, (list, tuple)):
        return value

    if type_name in ('color3', 'vector3', 'half3') and len(value) >= 3:
        return list(value[:3])
    if type_name in ('color4', 'vector4', 'half4'):
        if len(value) == 3:
            return [value[0], value[1], value[2], 1.0]
        if len(value) >= 4:
            return list(value[:4])
    if type_name in ('vector2', 'half2') and len(value) >= 2:
        return list(value[:2])
    if type_name in ('float', 'half', 'integer') and len(value) >= 1:
        return value[0]

    return value


def _create_convert_output(
    manifest: Dict[str, Any],
    stage,
    nodegraph_path: str,
    input_name: str,
    source_output,
    from_type: str,
    to_type: str,
    diagnostics=None,
):
    """Create a convert node output between two MaterialX types."""
    from_type = (from_type or '').lower()
    to_type = (to_type or '').lower()
    if from_type == to_type:
        return source_output

    nodedef_name = select_nodedef_name_for_node(
        manifest,
        "convert",
        input_type=from_type,
        output_type=to_type,
    )
    if not nodedef_name:
        nodedef_name = f"ND_convert_{from_type}_{to_type}"
        if diagnostics:
            diagnostics.add_warning(
                f"Falling back to '{nodedef_name}' for conversion {from_type} -> {to_type}. "
                "No matching nodedef was found; output may be invalid."
            )
    convert_name = _convert_shader_name(stage, nodegraph_path, input_name)
    convert_prim = stage.DefinePrim(f"{nodegraph_path}/{convert_name}", "Shader")
    convert_shader = UsdShade.Shader(convert_prim)
    convert_shader.CreateIdAttr(nodedef_name)

    in_type = _map_mtlx_type_to_sdf(from_type) or source_output.GetTypeName()
    out_type = _map_mtlx_type_to_sdf(to_type) or source_output.GetTypeName()

    in_input = convert_shader.CreateInput("in", in_type)
    in_input.ConnectToSource(source_output)
    if diagnostics:
        diagnostics.add_warning(
            f"Inserted convert node '{nodedef_name}' for {input_name}: {from_type} -> {to_type}."
        )
    return convert_shader.CreateOutput("out", out_type)
