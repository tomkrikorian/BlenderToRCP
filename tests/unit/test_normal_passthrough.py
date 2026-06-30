"""Unit tests for normal-map passthrough capture in the bake path.

The bake never renders a normal pass, so a source normal map must be carried
through onto the baked material rather than dropped (which left baked surfaces
flat and over-glossy). These tests pin the capture logic in
``_source_normal_passthrough``; the actual node wiring is verified end-to-end.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# bake_textures does ``import bpy`` at module scope; stub it for plain pytest.
sys.modules.setdefault("bpy", types.ModuleType("bpy"))

from Plugin.export.bake_textures import (  # noqa: E402
    _source_metallic_passthrough,
    _source_normal_passthrough,
)


class FakeImage:
    def __init__(self, name):
        self.name = name


class FakeSocket:
    def __init__(self, *, is_linked=False, default_value=0.0, from_node=None):
        self.is_linked = is_linked
        self.default_value = default_value
        self.links = [types.SimpleNamespace(from_node=from_node)] if from_node else []


class FakeInputs(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeNode:
    def __init__(self, node_type, *, image=None, uv_map="", inputs=None):
        self.type = node_type
        self.image = image
        self.uv_map = uv_map
        self.inputs = FakeInputs(inputs or {})


class FakeMaterial:
    use_nodes = True

    def __init__(self, nodes, principled):
        self.node_tree = types.SimpleNamespace(nodes=nodes)
        self._principled = principled


def _material(principled_inputs, extra_nodes):
    principled = FakeNode('BSDF_PRINCIPLED', inputs=principled_inputs)
    return FakeMaterial([principled, *extra_nodes], principled)


def test_captures_image_via_normal_map_node():
    img = FakeImage("wood_normal.png")
    tex = FakeNode('TEX_IMAGE', image=img, uv_map="UVMap")
    nmap = FakeNode(
        'NORMAL_MAP',
        uv_map="UVMap",
        inputs={'Strength': FakeSocket(default_value=0.8), 'Color': FakeSocket(is_linked=True, from_node=tex)},
    )
    mat = _material({'Normal': FakeSocket(is_linked=True, from_node=nmap)}, [nmap, tex])

    result = _source_normal_passthrough(mat)
    assert result is not None
    assert result["image"] is img
    assert result["strength"] == 0.8
    assert result["uv_layer"] == "UVMap"


def test_captures_image_wired_directly_to_normal_input():
    img = FakeImage("n.png")
    tex = FakeNode('TEX_IMAGE', image=img, uv_map="UV2")
    mat = _material({'Normal': FakeSocket(is_linked=True, from_node=tex)}, [tex])

    result = _source_normal_passthrough(mat)
    assert result is not None
    assert result["image"] is img
    assert result["strength"] == 1.0
    assert result["uv_layer"] == "UV2"


def test_none_when_normal_unlinked():
    mat = _material({'Normal': FakeSocket(is_linked=False)}, [])
    assert _source_normal_passthrough(mat) is None


def test_none_when_no_image_behind_normal_map():
    nmap = FakeNode('NORMAL_MAP', inputs={'Strength': FakeSocket(default_value=1.0), 'Color': FakeSocket(is_linked=False)})
    mat = _material({'Normal': FakeSocket(is_linked=True, from_node=nmap)}, [nmap])
    assert _source_normal_passthrough(mat) is None


def test_metallic_texture_is_captured():
    img = FakeImage("metal.png")
    tex = FakeNode('TEX_IMAGE', image=img, uv_map="UVMap")
    mat = _material({'Metallic': FakeSocket(is_linked=True, from_node=tex)}, [tex])
    result = _source_metallic_passthrough(mat)
    assert result is not None and result["image"] is img and result["uv_layer"] == "UVMap"


def test_metallic_nonzero_constant_is_captured():
    mat = _material({'Metallic': FakeSocket(is_linked=False, default_value=1.0)}, [])
    assert _source_metallic_passthrough(mat) == {"value": 1.0}


def test_metallic_zero_constant_is_skipped():
    # 0 equals the Principled default, so there is nothing to carry.
    mat = _material({'Metallic': FakeSocket(is_linked=False, default_value=0.0)}, [])
    assert _source_metallic_passthrough(mat) is None
