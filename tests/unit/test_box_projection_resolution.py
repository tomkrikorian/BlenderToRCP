"""Image Texture projection handling: BOX -> triplanar; SPHERE/TUBE refused.

Measured defect: every non-FLAT projection fell through to the FLAT path and
silently exported a UV-sampled image in place of the projection. BOX now maps
to ND_triplanarprojection_* (same file on filex/filey/filez, blend from the
node's Projection Blend, upaxis left at its default); SPHERE and TUBE are
refused with bake advice; a BOX texture fed by an effective Mapping transform
is refused precisely because place2d transforms 2D texture coordinates, not a
3D projection.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_bpy_stub = sys.modules.setdefault("bpy", types.ModuleType("bpy"))
if not hasattr(_bpy_stub, "types"):
    _bpy_stub.types = types.SimpleNamespace(NodeTree=object)

import pytest  # noqa: E402

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


class _Image:
    def __init__(self):
        self.filepath = "/assets/tex.png"
        self.filepath_raw = "/assets/tex.png"
        self.is_dirty = False
        self.source = "FILE"
        self.packed_file = None
        self.alpha_mode = "STRAIGHT"
        self.colorspace_settings = types.SimpleNamespace(name="sRGB")


def _image_node(projection="BOX", blend=0.4, vector_socket=None):
    node = _Node()
    node.type = "TEX_IMAGE"
    node.name = "Image Texture"
    node.projection = projection
    node.projection_blend = blend
    node.image = _Image()
    node.uv_map = ""
    node.extension = "REPEAT"
    node.interpolation = "Linear"
    node.inputs = {"Vector": vector_socket or _Socket(name="Vector")}
    return node


def _mapping_node(location=(0.25, 0.0, 0.0)):
    node = _Node()
    node.type = "MAPPING"
    node.name = "Mapping"
    node.vector_type = "POINT"
    node.inputs = {
        "Location": _Socket(list(location), name="Location"),
        "Rotation": _Socket([0.0, 0.0, 0.0], name="Rotation"),
        "Scale": _Socket([1.0, 1.0, 1.0], name="Scale"),
        "Vector": _Socket(name="Vector"),
    }
    return node


@pytest.fixture(autouse=True)
def _fake_image_path(monkeypatch):
    monkeypatch.setattr(
        core, "_resolve_image_path", lambda image: getattr(image, "filepath", None)
    )


def _resolve(node, output_name="Color", expected_type="color3"):
    output = _Socket(name=output_name)
    target = _Socket(linked=True, link=_Link(node, output))
    return core._resolve_socket_value(target, expected_type=expected_type)


def test_box_projection_authors_triplanar_with_same_file_on_all_axes():
    expr = _resolve(_image_node())
    assert expr["kind"] == "node"
    assert expr["node_id"] == "ND_triplanarprojection_color3"
    assert expr["node_id"] in _MANIFEST_NODES
    for axis in ("filex", "filey", "filez"):
        spec = expr["inputs"][axis]
        assert spec["type"] == "file_asset"
        assert spec["path"] == "/assets/tex.png"
        assert spec["colorspace"] == "srgb"
    # Neither `blend` nor `upaxis` exists on the triplanar nodedef RealityKit
    # binds at MaterialX 1.38, which is the version we declare. Authoring one
    # makes RealityKit discard the whole material's shader graph in silence, so
    # Blender's Projection Blend is dropped rather than expressed.
    assert "blend" not in expr["inputs"]
    assert "upaxis" not in expr["inputs"]


def test_box_projection_float_consumer_selects_the_float_variant():
    expr = _resolve(_image_node(), expected_type="float")
    assert expr["node_id"] == "ND_triplanarprojection_float"


def test_sphere_and_tube_projections_stay_refused_with_bake_advice():
    for projection in ("SPHERE", "TUBE"):
        expr = _resolve(_image_node(projection=projection))
        assert expr["kind"] == "unresolved", projection
        assert projection in expr["reason"]
        assert "bake" in expr["reason"].lower()


def test_box_with_effective_mapping_transform_is_refused_precisely():
    mapping = _mapping_node(location=(0.25, 0.0, 0.0))
    vector = _Socket(
        linked=True, link=_Link(mapping, _Socket(name="Vector")), name="Vector"
    )
    expr = _resolve(_image_node(vector_socket=vector))
    assert expr["kind"] == "unresolved"
    assert "Mapping transform" in expr["reason"]
    assert "place2d" in expr["reason"]


def test_box_with_identity_mapping_is_still_authored():
    mapping = _mapping_node(location=(0.0, 0.0, 0.0))
    vector = _Socket(
        linked=True, link=_Link(mapping, _Socket(name="Vector")), name="Vector"
    )
    expr = _resolve(_image_node(vector_socket=vector))
    assert expr["kind"] == "node"
    assert expr["node_id"] == "ND_triplanarprojection_color3"


def test_box_alpha_output_is_refused():
    expr = _resolve(_image_node(), output_name="Alpha", expected_type="float")
    assert expr["kind"] == "unresolved"
    assert "Alpha output" in expr["reason"]


def test_flat_projection_keeps_the_existing_texture_path():
    expr = _resolve(_image_node(projection="FLAT"))
    assert expr["kind"] == "texture"
    assert expr["path"] == "/assets/tex.png"


def test_validator_box_mapping_gate_matches_extraction():
    mapping = _mapping_node(location=(0.25, 0.0, 0.0))
    vector = _Socket(
        linked=True, link=_Link(mapping, _Socket(name="Vector")), name="Vector"
    )
    assert validate._box_projection_has_mapping(
        _image_node(vector_socket=vector)
    )

    identity = _mapping_node(location=(0.0, 0.0, 0.0))
    vector = _Socket(
        linked=True, link=_Link(identity, _Socket(name="Vector")), name="Vector"
    )
    assert not validate._box_projection_has_mapping(
        _image_node(vector_socket=vector)
    )
    assert not validate._box_projection_has_mapping(_image_node())
