"""Color Attribute (VERTEX_COLOR) -> ND_geompropvalue_color3 translation.

Blender 5.2's Color Attribute node (bl_idname ShaderNodeVertexColor, node
type VERTEX_COLOR) reads a mesh color attribute; Blender's USD exporter
writes that attribute as ``primvars:<attribute name>`` (verified against a
real Blender 5.2 export). The exact translation is a geompropvalue read of
the same name. Refused rather than approximated: an unnamed attribute, an
Alpha-output use, a name that is not a valid USD identifier, and a name no
mesh using the material carries (the read would dangle).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_bpy_stub = sys.modules.setdefault("bpy", types.ModuleType("bpy"))
if not hasattr(_bpy_stub, "types"):
    _bpy_stub.types = types.SimpleNamespace(NodeTree=object)

from Plugin.export.materials.extract import core  # noqa: E402
from Plugin.manifest.materialx_nodes import load_manifest  # noqa: E402
from Plugin.nodes import validate  # noqa: E402


_MANIFEST_NODES = frozenset(load_manifest()["nodes"].keys())


class _Socket:
    def __init__(self, value=None, *, linked=False, link=None, name="Value"):
        self.default_value = value
        self.is_linked = linked
        self.links = [link] if link is not None else []
        self.name = name


class _Link:
    def __init__(self, node, socket):
        self.from_node = node
        self.from_socket = socket


class _Node:
    pass


def _vertex_color_node(layer_name="MyColors"):
    node = _Node()
    node.type = "VERTEX_COLOR"
    node.name = "Color Attribute"
    node.layer_name = layer_name
    node.inputs = {}
    return node


def _resolve(node, output_name="Color", expected_type="color3", channel=None):
    output = _Socket(name=output_name)
    target = _Socket(linked=True, link=_Link(node, output))
    return core._resolve_socket_value(
        target, channel=channel, expected_type=expected_type
    )


def test_color_attribute_authors_geompropvalue_read():
    expr = _resolve(_vertex_color_node("MyColors"))
    assert expr["kind"] == "node"
    assert expr["node_id"] == "ND_geompropvalue_color3"
    assert expr["node_id"] in _MANIFEST_NODES
    assert expr["inputs"]["geomprop"] == {"kind": "constant", "value": "MyColors"}


def test_float_consumer_gets_blender_luminance_conversion():
    expr = _resolve(_vertex_color_node("MyColors"), expected_type="float")
    assert expr["node_id"] == "ND_swizzle_color3_float"
    luminance = expr["inputs"]["in"]
    assert luminance["node_id"] == "ND_luminance_color3"
    assert luminance["inputs"]["in"]["node_id"] == "ND_geompropvalue_color3"


def test_channel_consumer_gets_a_swizzle():
    expr = _resolve(
        _vertex_color_node("MyColors"), expected_type="float", channel="g"
    )
    assert expr["node_id"] == "ND_swizzle_color3_float"
    assert expr["inputs"]["channels"] == {"kind": "constant", "value": "g"}
    assert expr["inputs"]["in"]["node_id"] == "ND_geompropvalue_color3"


def test_unnamed_attribute_is_refused():
    expr = _resolve(_vertex_color_node(""))
    assert expr["kind"] == "unresolved"
    assert "names no color attribute" in expr["reason"]


def test_invalid_primvar_identifier_is_refused():
    expr = _resolve(_vertex_color_node("My Colors"))
    assert expr["kind"] == "unresolved"
    assert "not a valid USD primvar identifier" in expr["reason"]


def test_alpha_output_is_refused():
    expr = _resolve(_vertex_color_node("MyColors"), output_name="Alpha")
    assert expr["kind"] == "unresolved"
    assert "Alpha output" in expr["reason"]


def test_attribute_missing_from_meshes_is_refused(monkeypatch):
    monkeypatch.setattr(
        core, "_color_attribute_reaches_export", lambda node, name: False
    )
    expr = _resolve(_vertex_color_node("MyColors"))
    assert expr["kind"] == "unresolved"
    assert "primvars:MyColors" in expr["reason"]


def test_validator_moved_vertex_color_to_supported():
    assert "VERTEX_COLOR" in validate.SUPPORTED_TYPES
    assert "VERTEX_COLOR" not in validate.UNSUPPORTED_TYPES


def test_validator_flags_the_same_refusals(monkeypatch):
    node = _vertex_color_node("")
    node.outputs = {}
    issues = validate._vertex_color_issues(node)
    assert any("names no color attribute" in issue for issue in issues)

    node = _vertex_color_node("My Colors")
    node.outputs = {}
    issues = validate._vertex_color_issues(node)
    assert any("not a valid USD primvar identifier" in issue for issue in issues)

    monkeypatch.setattr(
        core, "_color_attribute_reaches_export", lambda node, name: False
    )
    node = _vertex_color_node("MyColors")
    node.outputs = {}
    issues = validate._vertex_color_issues(node)
    assert any("primvars:MyColors" in issue for issue in issues)


def test_validator_flags_a_linked_alpha_output():
    node = _vertex_color_node("MyColors")
    node.outputs = {"Alpha": _Socket(linked=True, name="Alpha")}
    issues = validate._vertex_color_issues(node)
    assert any("Alpha output" in issue for issue in issues)
