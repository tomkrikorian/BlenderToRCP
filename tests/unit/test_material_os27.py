"""Focused Blender 5.2 / Reality Composer Pro 3 material contract tests."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys
import types
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from Plugin.export.materials.author import create_materialx_material
from Plugin.export.materials.extract import core
from Plugin.export.materials import rewrite as material_rewrite
from Plugin.export.materials.graph import (
    MaterialXGraphBuilder,
    RCP3_PBR2_NODEDEF,
)
from Plugin.export.materials.textures import _create_texture_connection
from Plugin.export.usd_utils import PXR_AVAILABLE, Sdf, Usd, UsdShade
from Plugin.manifest.materialx_nodes import load_manifest

# Load the import-safe validator without executing Plugin.nodes.__init__, which
# imports Blender-only bpy modules unavailable to the OpenUSD unit-test Python.
_nodes_package = types.ModuleType("Plugin.nodes")
_nodes_package.__path__ = [str(REPO_ROOT / "Plugin" / "nodes")]
sys.modules.setdefault("Plugin.nodes", _nodes_package)
_validate_spec = importlib.util.spec_from_file_location(
    "Plugin.nodes.validate",
    REPO_ROOT / "Plugin" / "nodes" / "validate.py",
)
node_validate = importlib.util.module_from_spec(_validate_spec)
sys.modules["Plugin.nodes.validate"] = node_validate
_validate_spec.loader.exec_module(node_validate)


def _manifest():
    return load_manifest()


def test_manifest_records_rcp3_materialx_provenance_and_exact_pbr2_contract():
    manifest = _manifest()
    metadata = manifest["metadata"]
    assert metadata["profile"] == "realitykit-os27"
    assert metadata["materialx_reference_release"] == "1.39.4"
    assert metadata["reality_composer_pro"] == {
        "version": "3.0",
        # Verified 2026-07-30: every References nodedef is signature-identical
        # in the installed 80.0.1.500.1 libraries; the pin moved forward.
        "build": "80.0.1.500.1",
    }
    assert all(not Path(path).is_absolute() for path in metadata["source_files"])

    pbr2 = manifest["nodes"][RCP3_PBR2_NODEDEF]
    assert pbr2["node_version"] == "2.0"
    assert pbr2["is_default_version"] is True
    assert pbr2["target"] == "realitykit"
    assert pbr2["apple_availability"] == "visionOS 27.0; macOS 27.0; iOS 27.0"
    inputs = {item["name"]: item["type"] for item in pbr2["inputs"]}
    assert len(inputs) == 30
    assert inputs["baseDiffuseRoughness"] == "half"
    assert inputs["specularWeight"] == "half"
    assert manifest["nodes"]["ND_convert_float_half"]["outputs"][0]["type"] == "half"


def test_manifest_generation_is_deterministic(tmp_path):
    from scripts.build_materialx_manifest import build_manifest

    source = REPO_ROOT / "References" / "MaterialX-definitions"
    first = build_manifest(REPO_ROOT, source, include_half=False)
    second = build_manifest(REPO_ROOT, source, include_half=False)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_the_default_profile_is_pbr_surface_2_and_carries_sheen():
    """Build with no profile named: what a fresh scene gets.

    The default used to be the portable surface, which dropped this sheen on
    the floor. PBR Surface 2 carries it, and is verified by import.
    """
    graph = MaterialXGraphBuilder(_manifest()).build_pbr_material(
        {"base_color": [0.2, 0.3, 0.4], "sheen_color": [0.4, 0.2, 0.1]}
    )
    assert graph["surface_profile"] == "realitykit_pbr2"
    assert graph["nodes"][0]["node_id"] == "ND_realitykit_pbr_surfaceshader_2_0"
    assert "sheenColor" in graph["nodes"][0]["inputs"]


def test_explicit_pbr2_maps_blender_52_sheen_subsurface_and_specular_fields():
    graph = MaterialXGraphBuilder(_manifest()).build_pbr_material(
        {
            "base_color": [0.2, 0.3, 0.4],
            "diffuse_roughness": 0.15,
            "subsurface_weight": 0.6,
            "subsurface_radius": 0.005,
            "subsurface_radius_scale": [1.0, 0.2, 0.1],
            "subsurface_anisotropy": 0.25,
            "sheen_color": [0.4, 0.2, 0.1],
            "ior": 1.45,
            "anisotropic": 0.3,
            "anisotropic_rotation": 0.2,
            "specular_tint": [0.9, 0.8, 0.7],
            "specular_weight": 0.75,
            "clearcoat_ior": 1.6,
        }
    )
    assert graph["nodes"][0]["node_id"] == RCP3_PBR2_NODEDEF
    inputs = graph["nodes"][0]["inputs"]
    assert inputs["baseDiffuseRoughness"] == 0.15
    assert inputs["subsurfaceWeight"] == 0.6
    assert inputs["subsurfaceRadius"] == 0.005
    assert inputs["subsurfaceRadiusScale"] == [1.0, 0.2, 0.1]
    assert inputs["subsurfaceColor"] == [0.2, 0.3, 0.4]
    assert inputs["sheenColor"] == [0.4, 0.2, 0.1]
    assert inputs["specularIOR"] == 1.45
    assert inputs["specularWeight"] == 0.75


@pytest.mark.skipif(not PXR_AVAILABLE, reason="OpenUSD bindings required")
def test_pbr2_authors_real_half_types_and_materialx_profile_metadata():
    manifest = _manifest()
    graph = MaterialXGraphBuilder(manifest).build_pbr_material(
        {
            "base_color": [0.2, 0.3, 0.4],
            "diffuse_roughness": 0.2,
            "specular_weight": 0.8,
        }
    )
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)
    create_materialx_material(stage, "/Root/Material", "Material", graph, manifest)

    shader = UsdShade.Shader(stage.GetPrimAtPath("/Root/Material/pbr_surfaceshader_1"))
    assert shader.GetIdAttr().Get() == RCP3_PBR2_NODEDEF
    assert shader.GetInput("baseDiffuseRoughness").GetTypeName() == Sdf.ValueTypeNames.Half
    assert shader.GetInput("specularWeight").GetTypeName() == Sdf.ValueTypeNames.Half
    material = stage.GetPrimAtPath("/Root/Material")
    assert "MaterialXConfigAPI" in str(material.GetMetadata("apiSchemas"))
    assert material.GetAttribute("config:mtlx:version").Get() == "1.38"
    assert material.GetAttribute("colorSpace:name").Get() == "lin_rec709_scene"


def _float_node(value):
    return {
        "kind": "node",
        "node_id": "ND_multiply_float",
        "inputs": {
            "in1": {"kind": "constant", "value": float(value)},
            "in2": {"kind": "constant", "value": 1.0},
        },
    }


def _color_node(value):
    return {
        "kind": "node",
        "node_id": "ND_multiply_color3",
        "inputs": {
            "in1": {"kind": "constant", "value": list(value)},
            "in2": {"kind": "constant", "value": [1.0, 1.0, 1.0]},
        },
    }


@pytest.mark.skipif(not PXR_AVAILABLE, reason="OpenUSD bindings required")
def test_pbr2_direct_texture_and_linked_float_inputs_get_real_half_conversions():
    manifest = _manifest()
    graph = MaterialXGraphBuilder(
        manifest,
    ).build_pbr_material(
        {
            "base_color": [0.2, 0.3, 0.4],
            "input_graphs": {
                "baseDiffuseRoughness": {
                    "kind": "texture",
                    "path": "textures/diffuse-roughness.png",
                    "output_type": "float",
                    "channel": "r",
                    "colorspace": "raw",
                },
                "subsurfaceWeight": _float_node(0.25),
                "specularWeight": _float_node(0.8),
            },
        }
    )
    pbr = graph["nodes"][0]
    assert pbr["inputs"]["baseDiffuseRoughness"]["type"] == "texture"
    assert pbr["inputs"]["subsurfaceColor"] == [0.2, 0.3, 0.4]

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/Root", "Xform")
    stage.SetDefaultPrim(root)
    create_materialx_material(stage, "/Root/Material", "Material", graph, manifest)
    text = stage.GetRootLayer().ExportToString()
    assert text.count('info:id = "ND_convert_float_half"') >= 2
    assert "half inputs:baseDiffuseRoughness.connect" in text
    assert "half inputs:specularWeight.connect" in text


@pytest.mark.skipif(not PXR_AVAILABLE, reason="OpenUSD bindings required")
def test_texture_file_metadata_is_role_correct_and_unknown_spaces_fail_closed():
    stage = Usd.Stage.CreateInMemory()
    manifest = _manifest()
    _create_texture_connection(
        stage,
        "/Material",
        "baseColor",
        {
            "path": "textures/base.png",
            "type": "texture",
            "output_type": "color3",
            "colorspace": "srgb",
            "colorspace_role": "color",
        },
        manifest,
        "Material",
    )
    image = UsdShade.Shader(stage.GetPrimAtPath("/Material/Image"))
    assert image.GetInput("file").GetAttr().GetColorSpace() == "srgb_texture"

    _create_texture_connection(
        stage,
        "/Material",
        "roughness",
        {
            "path": "textures/orm.png",
            "type": "texture",
            "output_type": "float",
            "channel": "g",
            "colorspace": "raw",
            "colorspace_role": "data",
        },
        manifest,
        "Material",
    )
    # A packed scalar is read through the same three-channel reader every
    # working RealityKit package uses, and a data texture authors no color
    # space at all: an absent MaterialX color space is the no-transform
    # contract "raw" was meant to express, and RCP 3.0 replaces a material
    # whose reader carries the lowercase token with a striped placeholder.
    data_image = UsdShade.Shader(stage.GetPrimAtPath("/Material/Image_1"))
    assert data_image.GetIdAttr().Get() == "ND_image_color3"
    assert data_image.GetInput("file").GetAttr().GetColorSpace() == ""
    dot = UsdShade.Shader(stage.GetPrimAtPath("/Material/channel_roughness_g"))
    assert dot.GetIdAttr().Get() == "ND_dotproduct_vector3"
    assert tuple(dot.GetInput("in2").Get()) == (0.0, 1.0, 0.0)

    _create_texture_connection(
        stage,
        "/Material",
        "opacity",
        {
            "path": "textures/base.png",
            "type": "texture",
            "output_type": "float",
            "channel": "a",
            "colorspace": "srgb",
            "colorspace_role": "data",
            "source_has_alpha": True,
        },
        manifest,
        "Material",
    )
    # Alpha is the one genuine four-channel read. It uses ND_image_color4 plus
    # a convert/dotproduct component read - ND_separate4_color4 resolves in
    # RealityKit but has no Metal implementation.
    alpha_image = UsdShade.Shader(stage.GetPrimAtPath("/Material/Image_2"))
    assert alpha_image.GetIdAttr().Get() == "ND_image_color4"
    assert alpha_image.GetInput("file").GetAttr().GetColorSpace() == ""
    separate = UsdShade.Shader(stage.GetPrimAtPath("/Material/Image_2_a"))
    assert separate.GetIdAttr().Get() == "ND_dotproduct_vector4"
    assert tuple(separate.GetInput("in2").Get()) == (0.0, 0.0, 0.0, 1.0)

    with pytest.raises(ValueError, match="Unsupported Blender image color space"):
        _create_texture_connection(
            stage,
            "/Material",
            "baseColor2",
            {
                "path": "textures/wide.png",
                "type": "texture",
                "output_type": "color3",
                "colorspace": "unsupported:ACEScg",
                "colorspace_role": "color",
            },
            manifest,
            "Material",
        )


@pytest.mark.skipif(not PXR_AVAILABLE, reason="OpenUSD bindings required")
def test_cached_normal_texture_is_decoded_for_every_use():
    stage = Usd.Stage.CreateInMemory()
    manifest = _manifest()
    cache = {}
    spec = {
        "path": "textures/normal.png",
        "type": "normal_texture",
        "output_type": "vector3",
        "colorspace": "raw",
        "colorspace_role": "data",
    }
    first = _create_texture_connection(
        stage, "/Material", "normal", spec, manifest, "Material", cache
    )
    second = _create_texture_connection(
        stage, "/Material", "clearcoatNormal", spec, manifest, "Material", cache
    )
    assert UsdShade.Shader(first.GetPrim()).GetIdAttr().Get() == "ND_normal_map_decode"
    assert UsdShade.Shader(second.GetPrim()).GetIdAttr().Get() == "ND_normal_map_decode"


class _Socket:
    def __init__(self, value=None, *, linked=False, link=None, name=""):
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


class _Inputs(dict):
    """Minimal Blender socket collection: iterate values while supporting get/items."""

    def __iter__(self):
        return iter(self.values())


@pytest.mark.parametrize(
    ("blender_alpha_mode", "expected_alpha_mode", "expected_premultiplied"),
    [
        ("PREMUL", "premul", True),
        ("STRAIGHT", "straight", False),
    ],
)
def test_blender_image_alpha_semantics_reach_realitykit_graph(
    tmp_path,
    monkeypatch,
    blender_alpha_mode,
    expected_alpha_mode,
    expected_premultiplied,
):
    texture_path = tmp_path / "edge.png"
    texture_path.write_bytes(b"unit-test-image")
    image = SimpleNamespace(
        name="AssociatedAlphaEdge",
        filepath=str(texture_path),
        filepath_raw=str(texture_path),
        packed_file=None,
        source="FILE",
        is_dirty=False,
        file_format="PNG",
        alpha_mode=blender_alpha_mode,
        colorspace_settings=SimpleNamespace(name="sRGB"),
    )
    image_node = _Node()
    image_node.type = "TEX_IMAGE"
    image_node.name = "Premultiplied Base Color"
    image_node.image = image
    image_node.uv_map = ""
    image_node.inputs = {"Vector": _Socket()}
    color_output = _Socket(name="Color")
    alpha_output = _Socket(name="Alpha")

    principled = _Node()
    principled.type = "BSDF_PRINCIPLED"
    principled.name = "Principled BSDF"
    principled.inputs = {
        "Base Color": _Socket(
            (1.0, 1.0, 1.0, 1.0),
            linked=True,
            link=_Link(image_node, color_output),
            name="Base Color",
        ),
        "Alpha": _Socket(
            1.0,
            linked=True,
            link=_Link(image_node, alpha_output),
            name="Alpha",
        ),
    }
    material = SimpleNamespace(
        name="Associated Alpha",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[principled, image_node]),
        surface_render_method="BLENDED",
    )
    monkeypatch.setattr(core, "_get_surface_shader_node", lambda _material: principled)
    # pytest's tmp_path is itself inside the system temp root; this fixture is a
    # real existing source file, not an export-generated image snapshot.
    monkeypatch.setattr(core, "_is_temp_path", lambda _path: False)

    data = core.extract_blender_material_data(material)

    assert data["base_color_texture"] == str(texture_path.resolve())
    assert data["base_color_texture_alpha_mode"] == expected_alpha_mode
    assert bool(data.get("has_premultiplied_alpha")) is expected_premultiplied

    graph = MaterialXGraphBuilder(_manifest()).build_pbr_material(data)
    inputs = graph["nodes"][0]["inputs"]
    assert bool(inputs.get("hasPremultipliedAlpha")) is expected_premultiplied


def _extract_principled_base_expression(monkeypatch, expression):
    upstream = _Node()
    upstream.type = "MIX"
    upstream.name = "Base Color Expression"
    output = _Socket(name="Color")
    base_color = _Socket(
        (1.0, 1.0, 1.0, 1.0),
        linked=True,
        link=_Link(upstream, output),
        name="Base Color",
    )
    principled = _Node()
    principled.type = "BSDF_PRINCIPLED"
    principled.name = "Principled BSDF"
    principled.inputs = {
        "Base Color": base_color,
        "Alpha": _Socket(1.0, name="Alpha"),
    }
    material = SimpleNamespace(
        name="Nested Associated Alpha",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[principled, upstream]),
        blend_method="BLENDED",
    )
    monkeypatch.setattr(core, "_get_surface_shader_node", lambda _material: principled)
    monkeypatch.setattr(
        core,
        "_resolve_socket_value",
        lambda socket, **_kwargs: expression if socket is base_color else None,
    )
    return core.extract_blender_material_data(material)


def test_nested_premultiplied_base_color_sets_graph_semantics(monkeypatch):
    premultiplied = {
        "kind": "texture",
        "path": "/tmp/nested-premul.png",
        "output_type": "color3",
        "alpha_mode": "premul",
    }
    expression = {
        "kind": "node",
        "node_id": "ND_multiply_color3",
        "inputs": {
            "in1": premultiplied,
            "in2": {"kind": "constant", "value": [0.5, 0.5, 0.5]},
        },
    }

    data = _extract_principled_base_expression(monkeypatch, expression)

    assert data["base_color_texture_sources"] == [
        {"path": "/tmp/nested-premul.png", "alpha_mode": "premul"}
    ]
    assert data["has_premultiplied_alpha"] is True
    graph = MaterialXGraphBuilder(_manifest()).build_pbr_material(data)
    assert graph["nodes"][0]["inputs"]["hasPremultipliedAlpha"] is True


def test_mixed_premultiplied_and_straight_base_color_is_marked_ambiguous(
    monkeypatch,
):
    expression = {
        "kind": "node",
        "node_id": "ND_mix_color3",
        "inputs": {
            "fg": {
                "kind": "texture",
                "path": "/tmp/premul.png",
                "output_type": "color3",
                "alpha_mode": "premul",
            },
            "bg": {
                "kind": "texture",
                "path": "/tmp/straight.png",
                "output_type": "color3",
                "alpha_mode": "straight",
            },
            "mix": {"kind": "constant", "value": 0.5},
        },
    }

    data = _extract_principled_base_expression(monkeypatch, expression)

    assert data["base_color_texture_alpha_modes"] == ["premul", "straight"]
    assert "incompatible alpha conventions" in data[
        "base_color_alpha_semantics_error"
    ]
    assert "has_premultiplied_alpha" not in data


def test_rk_graph_ignores_premul_metadata_outside_surface_base_color():
    graph = {
        "nodes": [
            {
                "name": "Surface",
                "node_id": "ND_realitykit_pbr_surfaceshader",
                "inputs": {
                    "baseColor": {
                        "type": "texture",
                        "path": "/tmp/base.png",
                        "output_type": "color3",
                        "alpha_mode": "straight",
                    },
                    "normal": {
                        "type": "normal_texture",
                        "path": "/tmp/normal.png",
                        "output_type": "vector3",
                        "alpha_mode": "premul",
                    },
                },
            }
        ],
        "connections": [],
        "output": "Surface",
    }

    sources = core._rk_graph_base_color_texture_sources(graph)
    core._apply_base_color_texture_semantics(graph, sources)

    assert graph["base_color_texture_sources"] == [
        {"path": "/tmp/base.png", "alpha_mode": "straight"}
    ]
    assert "has_premultiplied_alpha" not in graph


def _validate_principled_inputs(
    inputs,
    *,
    normalize_unsupported_values=False,
):
    principled = _Node()
    principled.type = "BSDF_PRINCIPLED"
    principled.name = "Principled"
    principled.inputs = inputs
    material = SimpleNamespace(
        name="ProfileContract",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[principled]),
    )
    return node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
        normalize_unsupported_values=normalize_unsupported_values,
    )


@pytest.mark.parametrize(
    ("node_type", "property_name", "property_value", "stale_socket_value", "expected"),
    [
        ("INPUT_BOOL", "boolean", True, False, True),
        ("INPUT_INT", "integer", 7, 0, 7),
        ("INPUT_VECTOR", "vector", (1.25, 2.5, 3.75), (0.0, 0.0, 0.0), [1.25, 2.5, 3.75]),
    ],
)
def test_blender_52_function_constant_nodes_use_authoritative_node_properties(
    node_type,
    property_name,
    property_value,
    stale_socket_value,
    expected,
):
    node = _Node()
    node.type = node_type
    node.name = node_type
    setattr(node, property_name, property_value)
    if node_type == "INPUT_VECTOR":
        node.vector_dimensions = 3
    output = _Socket(stale_socket_value, name="Value")
    node.outputs = [output]
    target = _Socket(linked=True, link=_Link(node, output))
    assert core._resolve_socket_value(target) == {"kind": "constant", "value": expected}


def test_blender_52_function_constant_nodes_are_validated_as_supported():
    nodes = []
    for node_type in ("INPUT_BOOL", "INPUT_INT", "INPUT_VECTOR"):
        node = _Node()
        node.type = node_type
        node.name = node_type
        nodes.append(node)
    material = SimpleNamespace(
        name="Constants",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=nodes),
    )
    result = node_validate.validate_material(material, only_connected=False, strict=True)
    assert result["ok"] is True
    assert result["errors"] == []


def test_validator_allows_mapped_sheen_and_sss_but_not_transmission():
    """PBR Surface 2 carries sheen and subsurface; nothing carries transmission."""
    principled = _Node()
    principled.type = "BSDF_PRINCIPLED"
    principled.name = "Principled"
    principled.inputs = {
        "Thin Wall": _Socket(False),
        "Transmission Weight": _Socket(0.0),
        "Sheen Weight": _Socket(0.4),
        "Subsurface Weight": _Socket(0.2),
    }
    material = SimpleNamespace(
        name="Extended",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[principled]),
    )
    allowed = node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )
    assert allowed["ok"] is True

    principled.inputs["Transmission Weight"].default_value = 0.1
    blocked = node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )
    assert any("Transmission Weight" in issue["message"] for issue in blocked["errors"])


def test_stock_blender_52_principled_defaults_raise_nothing():
    inputs = {
        "Diffuse Roughness": _Socket(0.0),
        "Subsurface Weight": _Socket(0.0),
        "Subsurface Radius": _Socket((1.0, 0.2, 0.1)),
        "Subsurface Scale": _Socket(0.005),
        "Subsurface Anisotropy": _Socket(0.0),
        "IOR": _Socket(1.5),
        "Specular Tint": _Socket((1.0, 1.0, 1.0, 1.0)),
        "Coat Weight": _Socket(0.0),
        "Coat Roughness": _Socket(0.03),
        "Coat IOR": _Socket(1.5),
        "Coat Tint": _Socket((1.0, 1.0, 1.0, 1.0)),
        "Sheen Weight": _Socket(0.0),
        "Sheen Roughness": _Socket(0.5),
        "Sheen Tint": _Socket((1.0, 1.0, 1.0, 1.0)),
        "Subsurface IOR": _Socket(1.4),
        "Thin Film Thickness": _Socket(0.0),
        "Thin Film IOR": _Socket(1.33),
        "Anisotropic": _Socket(0.0),
        "Anisotropic Rotation": _Socket(0.0),
        "Tangent": _Socket((0.0, 0.0, 0.0)),
        "Transmission Weight": _Socket(0.0),
        "Thin Wall": _Socket(False),
    }

    result = _validate_principled_inputs(inputs)

    assert result["ok"] is True
    assert result["errors"] == []


@pytest.mark.parametrize("socket_name", ["Coat Weight", "Coat Roughness", "Coat Tint"])
def test_linked_coat_controls_fail_closed(socket_name):
    inputs = {socket_name: _Socket(0.5, linked=True)}
    if socket_name != "Coat Weight":
        inputs["Coat Weight"] = _Socket(0.5)
    result = _validate_principled_inputs(
        inputs,
    )

    assert result["ok"] is False
    assert any(
        socket_name in issue["message"] and "linked" in issue["message"]
        for issue in result["errors"]
    )


def test_pbr2_active_constant_coat_tint_fails_closed():
    result = _validate_principled_inputs(
        {
            "Coat Weight": _Socket(0.5),
            "Coat Tint": _Socket((0.8, 0.7, 0.6, 1.0)),
        },
    )

    assert result["ok"] is False
    assert any("Coat Tint" in issue["message"] for issue in result["errors"])


def test_unverified_active_specular_tint_is_rejected():
    result = _validate_principled_inputs(
        {"Specular Tint": _Socket((2.0, 2.0, 2.0, 1.0))},
    )

    assert result["ok"] is False
    assert any(
        "Specular Tint" in issue["message"] and "export-only" in issue["message"]
        for issue in result["errors"]
    )


def test_safe_achromatic_specular_tint_normalization_is_explicit_opt_in():
    result = _validate_principled_inputs(
        {"Specular Tint": _Socket((2.0, 2.0, 2.0, 1.0))},
        normalize_unsupported_values=True,
    )

    assert result["ok"] is True
    assert result["errors"] == []
    assert any(
        "Export-only normalization applied" in issue["message"]
        and ".blend file were not changed" in issue["message"]
        for issue in result["warnings"]
    )


@pytest.mark.parametrize(
    "socket",
    [
        _Socket((2.0, 1.5, 1.0, 1.0)),
        _Socket((2.0, 2.0, 2.0, 1.0), linked=True),
    ],
)
def test_colored_or_linked_specular_tint_cannot_be_auto_normalized(socket):
    result = _validate_principled_inputs(
        {"Specular Tint": socket},
        normalize_unsupported_values=True,
    )

    assert result["ok"] is False
    assert any(
        "cannot be normalized safely" in issue["message"]
        for issue in result["errors"]
    )


@pytest.mark.parametrize(
    ("socket_name", "active_value", "controller_name", "controller_value"),
    [
        ("Subsurface IOR", 1.5, "Subsurface Weight", 0.2),
        ("Thin Film Thickness", 0.1, None, None),
        ("Thin Film IOR", 1.5, "Thin Film Thickness", 0.1),
    ],
)
def test_unmapped_principled_controls_fail_closed(
    socket_name,
    active_value,
    controller_name,
    controller_value,
):
    inputs = {socket_name: _Socket(active_value)}
    if controller_name is not None:
        inputs[controller_name] = _Socket(controller_value)
    result = _validate_principled_inputs(
        inputs,
    )

    assert result["ok"] is False
    assert any(socket_name in issue["message"] for issue in result["errors"])


@pytest.mark.parametrize(
    ("socket_name", "active_value", "controller_name", "controller_value"),
    [
        ("Anisotropic", 0.4, None, None),
        ("Anisotropic Rotation", 0.25, "Anisotropic", 0.4),
        ("Tangent", (1.0, 0.0, 0.0), "Anisotropic", 0.4),
    ],
)
def test_unverified_anisotropy_mapping_fails_closed(
    socket_name,
    active_value,
    controller_name,
    controller_value,
):
    inputs = {socket_name: _Socket(active_value)}
    if controller_name is not None:
        inputs[controller_name] = _Socket(controller_value)
    result = _validate_principled_inputs(
        inputs,
    )

    assert result["ok"] is False
    assert any(socket_name in issue["message"] for issue in result["errors"])


def _normal_map_material(strength, space):
    normal_map = _Node()
    normal_map.type = "NORMAL_MAP"
    normal_map.name = "Normal Map"
    normal_map.inputs = {"Strength": _Socket(strength)}
    normal_map.convention = "OPENGL"
    normal_map.space = space
    return SimpleNamespace(
        name="PBR2Normal",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[normal_map]),
    )


def test_non_tangent_normal_space_fails_closed():
    result = node_validate.validate_material(
        _normal_map_material(1.0, "OBJECT"),
        only_connected=False,
        strict=True,
    )

    assert result["ok"] is False
    assert any("OBJECT" in issue["message"] for issue in result["errors"])


def test_constant_tangent_normal_strength_is_not_refused():
    """A constant Strength is authored as a tangent-space mix after the decode.

    The refusal used to be gated to PBR Surface 2 while the shipping surface
    applied the mix; with one surface the mix applies everywhere, so a routine
    Strength dial must not stop the export.
    """
    result = node_validate.validate_material(
        _normal_map_material(0.5, "TANGENT"),
        only_connected=False,
        strict=True,
    )

    assert not [issue for issue in result["errors"] if "Strength" in issue["message"]]


def test_blender_52_mapping_reads_location_rotation_and_scale_sockets():
    node = _Node()
    node.type = "MAPPING"
    node.name = "Mapping"
    node.vector_type = "POINT"
    node.inputs = {
        "Location": _Socket((0.125, 0.25, 0.0)),
        "Rotation": _Socket((0.0, 0.0, 0.5)),
        "Scale": _Socket((2.0, 3.0, 1.0)),
    }
    assert core._extract_mapping_from_node(node) == {
        "offset": (-0.125, -0.25),
        "rotate": 0.5,
        "scale": (0.5, 1.0 / 3.0),
        "pivot": (0.0, 0.0),
        "operationorder": 0,
    }
    node.inputs["Location"].is_linked = True
    with pytest.raises(ValueError, match="linked Location"):
        core._extract_mapping_from_node(node)


def test_blender_52_texture_mapping_uses_materialx_trs_inverse_contract():
    """TEXTURE mode applies the inverse transform, including the rotation.

    Measured on Blender 5.2 by baking the mapped coordinate itself: at
    rotation Z=90 deg, POINT sends (0.9, 0.06) to (-0.06, 0.9) while TEXTURE
    sends it to (0.06, -0.9) - i.e. rotate(-90). place2d TRS is
    rotate(theta)(uv - offset)/scale, so theta is negated. Previously only the
    offset sign flipped between the branches, which mirrored a rotated tiled
    decal about its pivot.
    """
    node = _Node()
    node.type = "MAPPING"
    node.name = "Texture Mapping"
    node.vector_type = "TEXTURE"
    node.inputs = {
        "Location": _Socket((0.2, 0.3, 0.0)),
        "Rotation": _Socket((0.0, 0.0, 0.5)),
        "Scale": _Socket((2.0, 4.0, 1.0)),
    }
    assert core._extract_mapping_from_node(node) == {
        "offset": (0.2, 0.3),
        "rotate": -0.5,
        "scale": (2.0, 4.0),
        "pivot": (0.0, 0.0),
        "operationorder": 1,
    }

    reroute = _Node()
    reroute.type = "REROUTE"
    reroute.inputs = [_Socket(linked=True, link=_Link(node, _Socket(name="Vector")))]
    assert core._extract_mapping_from_node(reroute)["operationorder"] == 1

    node.inputs["Scale"].default_value = (0.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="zero X/Y scale"):
        core._extract_mapping_from_node(node)


def _mapped_image_node(name, *, location, vector_type="POINT"):
    mapping = _Node()
    mapping.type = "MAPPING"
    mapping.name = f"{name} Mapping"
    mapping.vector_type = vector_type
    mapping.inputs = _Inputs({
        "Location": _Socket(tuple(location) + (0.0,)),
        "Rotation": _Socket((0.0, 0.0, 0.25)),
        "Scale": _Socket((2.0, 2.0, 1.0)),
        "Vector": _Socket(),
    })
    image = _Node()
    image.type = "TEX_IMAGE"
    image.name = name
    image.image = SimpleNamespace()
    image.uv_map = ""
    image.inputs = _Inputs({
        "Vector": _Socket(
            linked=True,
            link=_Link(mapping, _Socket(name="Vector")),
        )
    })
    return mapping, image


def _mapped_principled_material(name, mapped_images, extra_nodes=()):
    principled = _Node()
    principled.type = "BSDF_PRINCIPLED"
    principled.name = "Principled"
    principled.inputs = _Inputs({
        socket_name: _Socket(
            linked=True,
            link=_Link(image, _Socket(name="Color")),
        )
        for socket_name, _mapping, image in mapped_images
    })
    output = _Node()
    output.type = "OUTPUT_MATERIAL"
    output.name = "Material Output"
    output.is_active_output = True
    output.inputs = _Inputs({
        "Surface": _Socket(
            linked=True,
            link=_Link(principled, _Socket(name="BSDF")),
        ),
        "Volume": _Socket(),
        "Displacement": _Socket(),
    })
    nodes = [output, principled]
    for _socket_name, mapping, image in mapped_images:
        nodes.extend((mapping, image))
    nodes.extend(extra_nodes)
    return SimpleNamespace(
        name=name,
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=nodes),
    )


def test_strict_validation_allows_identical_base_and_roughness_mapping_nodes():
    base_mapping, base_image = _mapped_image_node(
        "Base Color", location=(0.1, 0.2)
    )
    rough_mapping, rough_image = _mapped_image_node(
        "Roughness", location=(0.1, 0.2)
    )
    material = _mapped_principled_material(
        "SharedMapping",
        (
            ("Base Color", base_mapping, base_image),
            ("Roughness", rough_mapping, rough_image),
        ),
    )

    result = node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )

    assert result["ok"] is True
    assert not any(
        "only the first 2D texture transform" in issue["message"]
        for issue in result["errors"]
    )


def test_strict_validation_rejects_distinct_base_and_roughness_mapping_nodes():
    base_mapping, base_image = _mapped_image_node(
        "Base Color", location=(0.1, 0.2)
    )
    rough_mapping, rough_image = _mapped_image_node(
        "Roughness", location=(0.3, 0.2)
    )
    material = _mapped_principled_material(
        "DistinctMappings",
        (
            ("Base Color", base_mapping, base_image),
            ("Roughness", rough_mapping, rough_image),
        ),
    )

    result = node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )

    assert result["ok"] is False
    assert any(
        "2 distinct non-default texture mappings" in issue["message"]
        for issue in result["errors"]
    )


def test_disconnected_distinct_mappings_do_not_trigger_authored_mapping_gate():
    unused_a_mapping, unused_a_image = _mapped_image_node(
        "Unused A", location=(0.1, 0.2)
    )
    unused_b_mapping, unused_b_image = _mapped_image_node(
        "Unused B", location=(0.4, 0.2)
    )
    material = _mapped_principled_material(
        "DisconnectedMappings",
        (),
        extra_nodes=(
            unused_a_mapping,
            unused_a_image,
            unused_b_mapping,
            unused_b_image,
        ),
    )

    result = node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )

    assert result["ok"] is True
    assert not any(
        "only the first 2D texture transform" in issue["message"]
        for issue in result["errors"]
    )


def _walk_expr(expr):
    if not isinstance(expr, dict):
        return
    yield expr
    for child in (expr.get("inputs") or {}).values():
        yield from _walk_expr(child)


def _ramp_expr(output_name="Color", interpolation="LINEAR", fac_value=0.0):
    fac = _Socket(fac_value)
    elements = [
        SimpleNamespace(position=0.1, color=(1.0, 0.0, 0.0, 0.2)),
        SimpleNamespace(position=0.35, color=(0.0, 1.0, 0.0, 0.6)),
        SimpleNamespace(position=0.8, color=(0.0, 0.0, 1.0, 1.0)),
    ]
    ramp = _Node()
    ramp.type = "VALTORGB"
    ramp.name = "Ramp"
    ramp.inputs = {"Fac": fac}
    ramp.color_ramp = SimpleNamespace(
        elements=elements,
        interpolation=interpolation,
        color_mode="RGB",
    )
    output = _Socket(name=output_name)
    target = _Socket(linked=True, link=_Link(ramp, output))
    return core._resolve_socket_value(target, expected_type="float" if output_name == "Alpha" else "color3")


@pytest.mark.parametrize("interpolation", ["LINEAR", "CONSTANT", "EASE"])
def test_color_ramp_preserves_all_stops_positions_and_supported_interpolation(interpolation):
    expr = _ramp_expr(interpolation=interpolation)
    constants = [node.get("value") for node in _walk_expr(expr) if node.get("kind") == "constant"]
    # Constant ramps change only at each following stop; the first stop's
    # position is mathematically irrelevant because Blender clamps below it.
    required_positions = (0.35, 0.8) if interpolation == "CONSTANT" else (0.1, 0.35, 0.8)
    assert all(position in constants for position in required_positions)
    assert [1.0, 0.0, 0.0] in constants
    assert [0.0, 1.0, 0.0] in constants
    assert [0.0, 0.0, 1.0] in constants


def test_color_ramp_alpha_uses_all_alpha_stops_as_float_values():
    expr = _ramp_expr(output_name="Alpha", interpolation="LINEAR")
    constants = [node.get("value") for node in _walk_expr(expr) if node.get("kind") == "constant"]
    assert 0.2 in constants and 0.6 in constants and 1.0 in constants
    assert not any(isinstance(value, list) and len(value) >= 3 for value in constants)


def test_color_ramp_spline_mode_fails_closed_for_baking():
    expr = _ramp_expr(interpolation="B_SPLINE")
    assert expr["kind"] == "unresolved"
    assert "requires baking" in expr["reason"]


def _eval_ramp_expr(expr):
    if expr["kind"] == "constant":
        return expr["value"]
    values = {name: _eval_ramp_expr(value) for name, value in expr["inputs"].items()}
    node_id = expr["node_id"]
    if "ifgreatereq" in node_id:
        return values["in1"] if values["value1"] >= values["value2"] else values["in2"]
    if "range_float" in node_id:
        denominator = values["inhigh"] - values["inlow"]
        value = (values["in"] - values["inlow"]) / denominator
        return max(values["outlow"], min(values["outhigh"], value))
    if "smoothstep_float" in node_id:
        value = (values["in"] - values["low"]) / (values["high"] - values["low"])
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)
    if "mix_" in node_id:
        mix = values["mix"]
        return [
            bg * (1.0 - mix) + fg * mix
            for bg, fg in zip(values["bg"], values["fg"])
        ]
    raise AssertionError(f"Unhandled ramp test node: {node_id}")


@pytest.mark.parametrize("interpolation", ["LINEAR", "EASE"])
def test_color_ramp_piecewise_boundaries_match_blender(interpolation):
    assert _eval_ramp_expr(_ramp_expr(interpolation=interpolation, fac_value=0.1)) == pytest.approx(
        [1.0, 0.0, 0.0]
    )
    assert _eval_ramp_expr(_ramp_expr(interpolation=interpolation, fac_value=0.35)) == pytest.approx(
        [0.0, 1.0, 0.0]
    )
    assert _eval_ramp_expr(_ramp_expr(interpolation=interpolation, fac_value=0.8)) == pytest.approx(
        [0.0, 0.0, 1.0]
    )
    assert _eval_ramp_expr(_ramp_expr(interpolation=interpolation, fac_value=0.225)) == pytest.approx(
        [0.5, 0.5, 0.0]
    )


def test_constant_color_ramp_switches_exactly_at_each_following_stop():
    assert _eval_ramp_expr(_ramp_expr(interpolation="CONSTANT", fac_value=0.349)) == [1.0, 0.0, 0.0]
    assert _eval_ramp_expr(_ramp_expr(interpolation="CONSTANT", fac_value=0.35)) == [0.0, 1.0, 0.0]
    assert _eval_ramp_expr(_ramp_expr(interpolation="CONSTANT", fac_value=0.8)) == [0.0, 0.0, 1.0]


def test_rgb_curves_uses_blender_52_r_g_b_combined_channel_order():
    source = _Node()
    source.type = "RGB"
    source.name = "Color"
    source_output = _Socket((0.2, 0.3, 0.4, 1.0), name="Color")
    source.outputs = {"Color": source_output}

    def curve(y):
        return SimpleNamespace(
            points=[
                SimpleNamespace(location=(0.0, 0.0)),
                SimpleNamespace(location=(1.0, y)),
            ]
        )

    curves = _Node()
    curves.type = "CURVE_RGB"
    curves.name = "RGB Curves"
    curves.inputs = {
        "Color": _Socket(linked=True, link=_Link(source, source_output)),
        "Fac": _Socket(1.0),
    }
    # Blender 5.2 source order is R, G, B, Combined.
    curves.mapping = SimpleNamespace(curves=[curve(0.1), curve(0.2), curve(0.3), curve(0.9)])
    target = _Socket(linked=True, link=_Link(curves, _Socket(name="Color")))
    expr = core._resolve_socket_value(target, expected_type="color3")

    assert expr["node_id"] == "ND_combine3_color3"
    for input_name, output_name, channel_y in (
        ("in1", "outr", 0.1),
        ("in2", "outg", 0.2),
        ("in3", "outb", 0.3),
    ):
        channel_curve = expr["inputs"][input_name]
        assert channel_curve["inputs"]["knots"]["value"][-1] == [1.0, channel_y]
        combined_curve = channel_curve["inputs"]["in"]
        assert combined_curve["inputs"]["knots"]["value"][-1] == [1.0, 0.9]
        separated = combined_curve["inputs"]["in"]
        assert separated["output"] == output_name


def test_rgb_curves_remains_strict_bake_required_until_rcp3_exactness_is_proven():
    node = _Node()
    node.type = "CURVE_RGB"
    node.name = "RGB Curves"
    material = SimpleNamespace(
        name="Curves",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[node]),
    )
    result = node_validate.validate_material(material, only_connected=False, strict=True)
    assert result["ok"] is False
    assert result["errors"][0]["node_type"] == "CURVE_RGB"


def test_diamond_graph_uses_branch_local_cycle_detection():
    shared = _Node()
    shared.type = "RGB"
    shared.name = "Shared"
    shared_output = _Socket((0.25, 0.5, 0.75, 1.0), name="Color")
    shared.outputs = {"Color": shared_output}

    def shared_input():
        return _Socket(linked=True, link=_Link(shared, shared_output))

    mix = _Node()
    mix.type = "MIX"
    mix.name = "Diamond"
    mix.blend_type = "MIX"
    mix.inputs = {
        "Factor": _Socket(0.5),
        "A": shared_input(),
        "B": shared_input(),
    }
    mix_output = _Socket(name="Result")
    target = _Socket(linked=True, link=_Link(mix, mix_output))
    expr = core._resolve_socket_value(target, expected_type="color3")
    assert expr["kind"] == "node"
    assert expr["inputs"]["bg"]["kind"] == "constant"
    assert expr["inputs"]["fg"]["kind"] == "constant"


def test_strict_validator_allows_the_same_resolvable_mix_subset_as_extractor():
    mix = _Node()
    mix.type = "MIX_RGB"
    mix.name = "Multiply"
    mix.blend_type = "MULTIPLY"
    mix.inputs = {
        "Fac": _Socket(0.5),
        "Color1": _Socket(linked=True),
        "Color2": _Socket(linked=True),
    }
    material = SimpleNamespace(
        name="Mix",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[mix]),
    )
    assert node_validate.validate_material(
        material,
        only_connected=False,
        strict=True,
    )["ok"] is True


def test_clean_packed_bytes_win_over_stale_external_file(tmp_path, monkeypatch):
    external = tmp_path / "texture.png"
    external.write_bytes(b"stale-external")
    image = SimpleNamespace(
        name="Packed",
        filepath=str(external),
        filepath_raw=str(external),
        packed_file=SimpleNamespace(data=b"authoritative-packed"),
        source="FILE",
        is_dirty=False,
        file_format="PNG",
    )
    monkeypatch.setattr(core, "_STAGED_IMAGE_CACHE", {})
    monkeypatch.setattr(core, "_STAGED_IMAGE_DIR", tmp_path / "stage")
    (tmp_path / "stage").mkdir()
    staged = Path(core._resolve_image_path(image))
    assert staged != external
    assert staged.read_bytes() == b"authoritative-packed"

    image.packed_file.data = b"repacked-current"
    restaged = Path(core._resolve_image_path(image))
    assert restaged == staged
    assert restaged.read_bytes() == b"repacked-current"


def test_dirty_image_refreshes_staging_cache(tmp_path, monkeypatch):
    image = SimpleNamespace(
        name="Dirty",
        filepath="",
        filepath_raw="",
        packed_file=SimpleNamespace(data=b"packed"),
        source="GENERATED",
        is_dirty=True,
        file_format="PNG",
    )
    state = {"bytes": b"first"}

    def save_snapshot(_image, destination):
        destination.write_bytes(state["bytes"])
        return True

    monkeypatch.setattr(core, "_save_current_image_snapshot_to_path", save_snapshot)
    monkeypatch.setattr(core, "_STAGED_IMAGE_CACHE", {})
    monkeypatch.setattr(core, "_STAGED_IMAGE_DIR", tmp_path / "stage")
    (tmp_path / "stage").mkdir()
    first = Path(core._resolve_image_path(image))
    assert first.read_bytes() == b"first"
    state["bytes"] = b"second"
    second = Path(core._resolve_image_path(image))
    assert second == first
    assert second.read_bytes() == b"second"
    assert second.suffix == ".png"


@pytest.mark.parametrize(("source", "dirty"), [("FILE", True), ("GENERATED", False)])
def test_current_pixel_snapshot_failure_never_falls_back_to_stale_bytes(
    tmp_path,
    monkeypatch,
    source,
    dirty,
):
    external = tmp_path / "stale.jpg"
    external.write_bytes(b"stale-disk")
    image = SimpleNamespace(
        name="CurrentPixels",
        filepath=str(external),
        filepath_raw=str(external),
        packed_file=SimpleNamespace(data=b"stale-packed"),
        source=source,
        is_dirty=dirty,
        is_float=False,
        file_format="JPEG",
    )
    monkeypatch.setattr(core, "_save_current_image_snapshot_to_path", lambda *_: False)
    monkeypatch.setattr(core, "_STAGED_IMAGE_CACHE", {})
    monkeypatch.setattr(core, "_STAGED_IMAGE_DIR", tmp_path / "stage")
    (tmp_path / "stage").mkdir()
    with pytest.raises(ValueError, match="Unable to snapshot"):
        core._resolve_image_path(image)


def test_packed_write_failure_never_falls_back_to_external_file(tmp_path, monkeypatch):
    external = tmp_path / "stale.png"
    external.write_bytes(b"stale-disk")
    image = SimpleNamespace(
        name="Packed",
        filepath=str(external),
        filepath_raw=str(external),
        packed_file=SimpleNamespace(data=b"current-packed"),
        source="FILE",
        is_dirty=False,
        file_format="PNG",
    )
    destination = tmp_path / "not-a-directory"
    destination.write_text("blocked")
    monkeypatch.setattr(core, "_STAGED_IMAGE_CACHE", {})
    monkeypatch.setattr(core, "_STAGED_IMAGE_DIR", destination)
    with pytest.raises((FileExistsError, ValueError)):
        core._resolve_image_path(image)


def test_standalone_emission_preserves_texture_metadata_current_pixels_and_strength(monkeypatch):
    color_socket = _Socket(linked=True, name="Color")
    strength_socket = _Socket(2.5, name="Strength")
    emission = _Node()
    emission.type = "EMISSION"
    emission.inputs = {"Color": color_socket, "Strength": strength_socket}
    material = SimpleNamespace(
        name="Emission",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[emission]),
    )
    monkeypatch.setattr(core, "_get_surface_shader_node", lambda _material: emission)
    monkeypatch.setattr(
        core,
        "_resolve_socket_value",
        lambda socket, **_kwargs: {
            "kind": "texture",
            "path": "/tmp/current-emission.png",
            "uv_map": "DetailUV",
            "mapping": {"offset": (0.1, 0.2), "scale": (0.5, 0.5)},
            "colorspace": "lin_rec709",
            "alpha_mode": "straight",
            "current_pixel_snapshot": True,
        }
        if socket is color_socket
        else None,
    )
    data = core.extract_blender_material_data(material)
    expr = data["input_graphs"]["color"]
    assert expr["path"] == "/tmp/current-emission.png"
    assert expr["uv_map"] == "DetailUV"
    assert expr["mapping"]["offset"] == (0.1, 0.2)
    assert expr["colorspace"] == "lin_rec709"
    assert expr["alpha_mode"] == "straight"
    assert expr["scale"] == 2.5
    assert data["native_preview_stale"] is True

    graph = MaterialXGraphBuilder(_manifest()).build_unlit_material(data)
    texture = graph["nodes"][0]["inputs"]["color"]
    assert texture["texcoord"] == "DetailUV"
    assert texture["colorspace"] == "lin_rec709"
    assert texture["scale"] == 2.5


def test_disconnected_emission_never_replaces_an_unsupported_active_shader(monkeypatch):
    active = _Node()
    active.type = "BSDF_GLASS"
    orphan = _Node()
    orphan.type = "EMISSION"
    orphan.inputs = {"Color": _Socket((1.0, 0.0, 0.0, 1.0)), "Strength": _Socket(10.0)}
    material = SimpleNamespace(
        name="Unsupported",
        use_nodes=True,
        node_tree=SimpleNamespace(nodes=[active, orphan]),
    )
    monkeypatch.setattr(core, "_get_surface_shader_node", lambda _material: active)
    assert core.extract_blender_material_data(material)["type"] == "unknown"


def test_principled_linked_emission_color_and_strength_are_multiplied():
    payload = {
        "base_color": [0.2, 0.3, 0.4],
        "emission_color": [0.1, 0.2, 0.3],
        "input_graphs": {
            "_emissionColor": _color_node([0.8, 0.6, 0.4]),
            "_emissionStrength": _float_node(3.0),
        },
    }
    graph = MaterialXGraphBuilder(_manifest()).build_pbr_material(payload)
    emission_connections = [
        connection
        for connection in graph["connections"]
        if connection["to_input"] == "emissiveColor"
    ]
    assert len(emission_connections) == 1


@pytest.mark.skipif(not PXR_AVAILABLE, reason="OpenUSD bindings required")
def test_stale_preview_network_is_pruned_without_removing_mtlx_network():
    stage = Usd.Stage.CreateInMemory()
    material = UsdShade.Material(stage.DefinePrim("/Material", "Material"))

    preview = UsdShade.Shader(stage.DefinePrim("/Material/Preview", "Shader"))
    preview.CreateIdAttr("UsdPreviewSurface")
    texture = UsdShade.Shader(stage.DefinePrim("/Material/StaleTexture", "Shader"))
    texture.CreateIdAttr("UsdUVTexture")
    texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set("stale.png")
    texture_output = texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(texture_output)
    material.CreateSurfaceOutput().ConnectToSource(
        preview.CreateOutput("surface", Sdf.ValueTypeNames.Token)
    )

    mtlx = UsdShade.Shader(stage.DefinePrim("/Material/CurrentMtlx", "Shader"))
    mtlx.CreateIdAttr("ND_realitykit_pbr_surfaceshader")
    material.CreateSurfaceOutput("mtlx").ConnectToSource(
        mtlx.CreateOutput("out", Sdf.ValueTypeNames.Token)
    )

    material_rewrite._remove_stale_preview_network(stage, material)
    assert not stage.GetPrimAtPath("/Material/Preview").IsValid()
    assert not stage.GetPrimAtPath("/Material/StaleTexture").IsValid()
    assert stage.GetPrimAtPath("/Material/CurrentMtlx").IsValid()
    assert material.GetSurfaceOutput().GetAttr().GetConnections() == []


def test_unlit_surface_never_receives_pbr_only_graph_inputs():
    """build_unlit_material used to pass input_graphs through unfiltered.

    input_graphs is keyed for the PBR surface. ND_realitykit_unlit_surfaceshader
    declares only color/opacity/opacityThreshold/applyPostProcessToneMap/
    hasPremultipliedAlpha, so authoring roughness, metallic or the private
    _emissionColor produced a shader prim carrying inputs its nodedef does not
    define. author.py records an error for each but does not raise, so the
    rewrite never rolled back and the export failed later with an opaque
    diagnostics-gate message instead of at the cause.
    """
    manifest = _manifest()
    unlit_def = manifest["nodes"]["ND_realitykit_unlit_surfaceshader"]
    declared = {entry["name"] for entry in unlit_def["inputs"]}

    data = {
        "base_color": [1.0, 1.0, 1.0],
        "is_transparent": True,
        "input_graphs": {
            "baseColor": {"kind": "constant", "type": "color3", "value": [0.5, 0.2, 0.1]},
            "opacity": {"kind": "constant", "type": "float", "value": 0.7},
            "roughness": {"kind": "constant", "type": "float", "value": 0.42},
            "metallic": {"kind": "constant", "type": "float", "value": 1.0},
            "_emissionColor": {"kind": "constant", "type": "color3", "value": [1, 0, 0]},
        },
    }

    graph = MaterialXGraphBuilder(manifest).build_unlit_material(data)
    authored = set(graph["nodes"][0]["inputs"])

    unknown = authored - declared
    assert not unknown, (
        f"unlit surface authored inputs its nodedef does not declare: {sorted(unknown)}"
    )
    # baseColor is the one name that differs between the two surfaces.
    assert "color" in authored
    assert "opacity" in authored


def test_unlit_omitted_graph_inputs_are_reported():
    class _Diagnostics:
        def __init__(self):
            self.warnings = []

        def add_warning(self, message):
            self.warnings.append(message)

    diagnostics = _Diagnostics()
    data = {
        "base_color": [1.0, 1.0, 1.0],
        "input_graphs": {
            "roughness": {"kind": "constant", "type": "float", "value": 0.42},
        },
    }

    MaterialXGraphBuilder(_manifest(), diagnostics=diagnostics).build_unlit_material(data)

    assert any("roughness" in message for message in diagnostics.warnings), (
        "dropping a linked input silently is how the PBR2 profile bugs hid"
    )


class _CollectingDiagnostics:
    def __init__(self):
        self.warnings = []

    def add_warning(self, message):
        self.warnings.append(message)


# ---------------------------------------------------------------------------
# RealityKit node-group textures must declare a colour-space role.
#
# textures._materialx_file_colorspace only enforces "data textures must be
# Non-Color/raw" when the spec carries colorspace_role == "data". Neither RK
# extraction path set it, so a normal or roughness image left at Blender's
# default sRGB was authored srgb_texture and silently sRGB-decoded by
# RealityKit - while the Principled path fails closed on exactly that input.
# ---------------------------------------------------------------------------


class _RKSocket:
    def __init__(self, name):
        self.name = name
        self.is_linked = True


def _extract_group_texture_specs(monkeypatch, socket_names):
    """Drive the real _extract_group_inputs with linked image sockets."""
    monkeypatch.setattr(core, "_extract_image_path_from_socket", lambda s: "/tmp/t.png")
    monkeypatch.setattr(core, "_socket_output_type", lambda s: "color3")
    monkeypatch.setattr(core, "_extract_uv_map_from_socket", lambda s: None)
    monkeypatch.setattr(core, "_extract_mapping_from_socket", lambda s: None)
    monkeypatch.setattr(core, "_extract_colorspace_from_socket", lambda s: "sRGB")
    monkeypatch.setattr(core, "_extract_alpha_mode_from_socket", lambda s: None)
    group = SimpleNamespace(inputs=[_RKSocket(name) for name in socket_names])
    return core._extract_group_inputs(group)


def test_rk_group_data_textures_are_tagged_as_data(monkeypatch):
    specs = _extract_group_texture_specs(monkeypatch, ["normal", "roughness"])

    assert specs["normal"]["colorspace_role"] == "data"
    assert specs["roughness"]["colorspace_role"] == "data"


def test_rk_group_colour_textures_are_tagged_as_colour(monkeypatch):
    specs = _extract_group_texture_specs(monkeypatch, ["baseColor", "emissiveColor"])

    assert specs["baseColor"]["colorspace_role"] == "color"
    assert specs["emissiveColor"]["colorspace_role"] == "color"


def test_srgb_tagged_data_texture_now_fails_closed(monkeypatch):
    """The guard the missing role used to bypass."""
    from Plugin.export.materials import textures as mtlx_textures

    specs = _extract_group_texture_specs(monkeypatch, ["normal"])
    with pytest.raises(ValueError):
        mtlx_textures._materialx_file_colorspace(specs["normal"], "normal")


def test_point_and_texture_mapping_rotate_in_opposite_directions():
    """The two modes are inverses; a shared rotation sign cannot be right.

    Guards the specific regression: both branches used to emit +rotation[2].
    """
    def mapping_for(vector_type):
        node = _Node()
        node.type = "MAPPING"
        node.name = "Mapping"
        node.vector_type = vector_type
        node.inputs = {
            "Location": _Socket((0.0, 0.0, 0.0)),
            "Rotation": _Socket((0.0, 0.0, 0.75)),
            "Scale": _Socket((1.0, 1.0, 1.0)),
        }
        return core._extract_mapping_from_node(node)

    point = mapping_for("POINT")
    texture = mapping_for("TEXTURE")

    assert point["rotate"] == 0.75
    assert texture["rotate"] == -0.75
    assert point["rotate"] == -texture["rotate"]
