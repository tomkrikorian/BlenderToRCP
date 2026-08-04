"""Procedural textures must sample spatially varying coordinates.

Measured defect: a Noise/Voronoi/Gradient texture with its Vector unwired
exported successfully with no warning, but the authored position/texcoord was
the socket default constant (0, 0, 0) - the pattern was sampled at a single
point and rendered flat. ``_expr_from_socket`` folds an unlinked socket to its
default value, so the intended ``_default_texcoord_expr`` fallback was dead
code.

Blender samples an unwired Vector with Generated coordinates
(object-bounding-box normalized). The manifest's runtime-resolvable stand-in
is object-space position (ND_position_vector3); the deliberate approximation
is named by an always-on warning in ``collect_material_warnings``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_bpy_stub = sys.modules.setdefault("bpy", types.ModuleType("bpy"))
if not hasattr(_bpy_stub, "types"):
    _bpy_stub.types = types.SimpleNamespace(NodeTree=object)

from Plugin.export.materials.extract import core  # noqa: E402
from Plugin.manifest.materialx_nodes import load_manifest  # noqa: E402


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


def _walk_expr(expr):
    if not isinstance(expr, dict):
        return
    yield expr
    for child in (expr.get("inputs") or {}).values():
        yield from _walk_expr(child)


def _resolve_from(node, output_name="Fac", expected_type="float"):
    output = _Socket(name=output_name)
    target = _Socket(linked=True, link=_Link(node, output))
    return core._resolve_socket_value(target, expected_type=expected_type)


def _noise_node(vector_socket=None):
    node = _Node()
    node.type = "TEX_NOISE"
    node.name = "Noise Texture"
    node.inputs = {
        "Vector": vector_socket or _Socket([0.0, 0.0, 0.0], name="Vector"),
        "Scale": _Socket(7.0),
        "Detail": _Socket(2.0),
        "Roughness": _Socket(0.5),
        "Distortion": _Socket(0.0),
    }
    return node


def _voronoi_node(scale=4.0):
    node = _Node()
    node.type = "TEX_VORONOI"
    node.name = "Voronoi Texture"
    node.inputs = {
        "Vector": _Socket([0.0, 0.0, 0.0], name="Vector"),
        "Scale": _Socket(scale),
        "Randomness": _Socket(1.0),
    }
    return node


def _gradient_node():
    node = _Node()
    node.type = "TEX_GRADIENT"
    node.name = "Gradient Texture"
    node.inputs = {"Vector": _Socket([0.0, 0.0, 0.0], name="Vector")}
    return node


def _assert_is_object_position(expr):
    assert isinstance(expr, dict) and expr.get("kind") == "node", expr
    assert expr["node_id"] == "ND_position_vector3"
    assert expr["inputs"]["space"] == {"kind": "constant", "value": "object"}


def test_noise_unwired_vector_authors_position_not_a_constant():
    expr = _resolve_from(_noise_node())
    assert expr["kind"] == "node"
    # fractal3d, not unifiednoise3d: the latter exists only in RealityKit's
    # MaterialX 1.39 store while this profile declares 1.38, where a missing
    # nodedef silently costs the material its whole shader graph. Measured with
    # realitytool compile: the old shape produced 0 shadergraphs and 1 PBR
    # fallback; this one produces 1 and 0.
    assert expr["node_id"] == "ND_fractal3d_float"
    # fractal3d has no frequency input, so Scale folds into the sample position
    # exactly as it does for Voronoi below.
    position = expr["inputs"]["position"]
    assert position["node_id"] == "ND_multiply_vector3"
    _assert_is_object_position(position["inputs"]["in1"])
    assert position["inputs"]["in2"]["node_id"] == "ND_combine3_vector3"


def test_voronoi_unwired_vector_authors_scaled_position():
    expr = _resolve_from(_voronoi_node(scale=4.0))
    assert expr["node_id"] == "ND_worleynoise3d_float"
    position = expr["inputs"]["position"]
    # Blender applies Scale to the sample position; worleynoise3d has no
    # frequency input, so it must be an explicit multiply.
    assert position["node_id"] == "ND_multiply_vector3"
    _assert_is_object_position(position["inputs"]["in1"])
    scale_vector = position["inputs"]["in2"]
    assert scale_vector["node_id"] == "ND_combine3_vector3"
    assert scale_vector["inputs"]["in1"] == {"kind": "constant", "value": 4.0}


def test_voronoi_unit_scale_skips_the_multiply():
    expr = _resolve_from(_voronoi_node(scale=1.0))
    _assert_is_object_position(expr["inputs"]["position"])


def test_gradient_unwired_vector_authors_converted_position():
    expr = _resolve_from(_gradient_node())
    assert expr["node_id"] == "ND_ramplr_float"
    texcoord = expr["inputs"]["texcoord"]
    assert texcoord["node_id"] == "ND_convert_vector3_vector2"
    _assert_is_object_position(texcoord["inputs"]["in"])


def test_every_authored_procedural_nodedef_is_manifest_backed():
    for node in (_noise_node(), _voronoi_node(), _gradient_node()):
        expr = _resolve_from(node)
        for part in _walk_expr(expr):
            if part.get("kind") == "node":
                assert part["node_id"] in _MANIFEST_NODES, part["node_id"]


def test_unresolvable_wired_vector_still_refuses():
    bad = _Node()
    bad.type = "LIGHT_PATH"
    bad.name = "Light Path"
    bad.inputs = {}
    bad_output = _Socket(name="Is Camera Ray")
    vector_socket = _Socket(linked=True, link=_Link(bad, bad_output), name="Vector")
    expr = _resolve_from(_noise_node(vector_socket=vector_socket))
    assert expr["kind"] == "unresolved"


def test_procedural_translation_always_warns():
    warnings = _collect_warnings_for_node_types(
        ["TEX_NOISE", "TEX_VORONOI", "TEX_GRADIENT"]
    )
    procedural = [w for w in warnings if "pixel-for-pixel" in w]
    assert len(procedural) == 3, warnings
    # The sweep's capability-noise contract must not be violated by the
    # intentional-approximation warning.
    for warning in procedural:
        lowered = warning.lower()
        for term in ("unrecognized", "requires baking", "limited support"):
            assert term not in lowered, warning


class _TreeNode:
    def __init__(self, node_type, name, inputs=()):
        self.type = node_type
        self.name = name
        self.inputs = list(inputs)


class _OutputInputs:
    def __init__(self, surface_socket):
        self._surface_socket = surface_socket

    def get(self, name):
        return self._surface_socket if name == "Surface" else None


def _collect_warnings_for_node_types(node_types):
    surface = _TreeNode("BSDF_PRINCIPLED", "Principled BSDF")
    upstream = [
        _TreeNode(node_type, f"{node_type.title()} {index}")
        for index, node_type in enumerate(node_types)
    ]
    surface.inputs = [
        SimpleNamespace(is_linked=True, links=[SimpleNamespace(from_node=node)])
        for node in upstream
    ]

    output = _TreeNode("OUTPUT_MATERIAL", "Material Output")
    output.is_active_output = True
    output.inputs = _OutputInputs(
        SimpleNamespace(is_linked=True, links=[SimpleNamespace(from_node=surface)])
    )

    material = SimpleNamespace(
        name="ProceduralWarnings",
        use_nodes=True,
        node_tree=SimpleNamespace(
            nodes=[surface, *upstream, output],
            links=[],
        ),
    )
    return core.collect_material_warnings(material)
