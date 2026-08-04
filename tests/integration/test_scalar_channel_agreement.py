"""Integration - both halves of a material must read the same texture channel.

Every material we export carries two networks over the same textures: the
MaterialX graph RealityKit renders, and the retained UsdPreviewSurface network
Blender's own exporter writes for Quick Look. When a scalar input (roughness,
metallic, ambient occlusion) is driven by a plain colour texture, each half has
to decide which channel of that texture is the scalar.

They disagreed. The MaterialX half hardcoded ``g`` for roughness while the
preview half - and RealityKit's own USD importer, which names the node
``swizzle_roughness_r`` - read ``r``. On a grayscale map that is invisible; on
any chromatic map the two renderers showed different surfaces from one file.

This test does not pin a literal. It reads the channel each half actually chose
and asserts they match, so the two networks cannot drift apart again regardless
of which channel turns out to be right.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

#: A deliberately chromatic texture: if the two halves read different channels
#: they get different numbers, which is the whole point of the scene.
_BUILD = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
texture = sys.argv[sys.argv.index("--") + 2]

bpy.ops.wm.read_factory_settings(use_empty=True)

image = bpy.data.images.new("chroma", 8, 8)
pixels = []
for i in range(8 * 8):
    pixels += [0.9, 0.4, 0.1, 1.0]   # r != g != b, so a channel swap shows
image.pixels = pixels
image.filepath_raw = texture
image.file_format = 'PNG'
image.save()
bpy.data.images.remove(image)

def plane(name, x, socket):
    bpy.ops.mesh.primitive_plane_add(location=(x, 0, 0))
    obj = bpy.context.active_object
    obj.name = "Obj_" + name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    obj.data.materials.append(material)
    tree = material.node_tree
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(texture)
    node.image.colorspace_settings.name = 'Non-Color'
    tree.links.new(
        node.outputs["Color"],
        tree.nodes["Principled BSDF"].inputs[socket],
    )

plane("RoughMat", 0.0, "Roughness")
plane("MetalMat", 3.0, "Metallic")

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


def _material_scope(text: str, material_name: str) -> str:
    match = re.search(
        rf'def Material "{material_name}".*?(?=\n        def Material |\Z)',
        text,
        re.S,
    )
    assert match, f"material {material_name} not found"
    return match.group(0)


@pytest.fixture(scope="module")
def channel_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("channels")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "channels.blend"
    texture = workdir / "chroma.png"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), str(texture)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    stage = workdir / "out" / "channels.usda"
    stage.parent.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"),
         "export", str(blend), "-o", str(stage), "--format", "USDA"],
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return stage.read_text()


def _preview_channel(scope: str, input_name: str) -> str:
    """The UsdUVTexture output name Blender's exporter connected."""
    match = re.search(rf'inputs:{input_name}\.connect = [^\n]*\.outputs:(\w+)', scope)
    assert match, f"preview network does not drive {input_name} from a texture"
    return match.group(1)


def _materialx_channel(scope: str, input_name: str) -> str:
    """The `channels` string on the swizzle feeding the MaterialX surface."""
    surface = re.search(
        rf'inputs:{input_name}\.connect = </[^>]*/(\w+)\.outputs:out>', scope
    )
    assert surface, f"MaterialX network does not drive {input_name} from a node"
    node = re.search(
        rf'def Shader "{surface.group(1)}"\s*\{{(.*?)\n            \}}', scope, re.S
    )
    assert node, f"node {surface.group(1)} not found"
    channels = re.search(r'string inputs:channels = "(\w+)"', node.group(1))
    assert channels, f"node {surface.group(1)} authors no channels"
    return channels.group(1)


@pytest.mark.parametrize(
    ("material", "input_name"),
    [("RoughMat", "roughness"), ("MetalMat", "metallic")],
)
def test_both_networks_read_the_same_channel(channel_export, material, input_name):
    scope = _material_scope(channel_export, material)
    preview = _preview_channel(scope, input_name)
    materialx = _materialx_channel(scope, input_name)
    assert materialx == preview, (
        f"{material}.{input_name}: MaterialX reads '{materialx}' but the "
        f"retained preview network reads '{preview}' from the same texture"
    )


@pytest.mark.parametrize("material", ["RoughMat", "MetalMat"])
def test_the_agreed_channel_is_red(channel_export, material):
    """Red is what RealityKit's own USD importer picks, and what every channel
    extraction in the shipping RCP material corpus uses."""
    scope = _material_scope(channel_export, material)
    assert _preview_channel(
        scope, "roughness" if material == "RoughMat" else "metallic"
    ) == "r"
