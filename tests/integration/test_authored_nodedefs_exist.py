"""Integration test — every authored MaterialX info:id exists in the manifest.

Measured before the fix: `Image Texture -> RGB to BW -> Roughness` exported
`ok: true` while authoring two fabricated nodedefs —

    MISSING  ND_convert_color3_float
    MISSING  ND_convert_vector4_color3

MaterialX has no color3->float convert at all; the name was invented by string
formatting when the hardened selector correctly returned None, and nothing
downstream loaded the manifest to notice. RealityKit cannot bind a shader whose
nodedef does not exist.

The correct translation, now authored: luminance (idempotent on the grayscale
RGB-to-BW output) followed by a channel swizzle — which is exactly Blender's
own implicit colour-to-float conversion (linear RGB to gray).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

_BUILD = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
texture = sys.argv[sys.argv.index("--") + 2]

bpy.ops.wm.read_factory_settings(use_empty=True)

image = bpy.data.images.new("rough", 8, 8)
image.generated_color = (0.5, 0.5, 0.5, 1.0)
image.filepath_raw = texture
image.file_format = 'PNG'
image.save()
bpy.data.images.remove(image)

loaded = bpy.data.images.load(texture)
loaded.colorspace_settings.name = 'Non-Color'

bpy.ops.mesh.primitive_plane_add()
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project()
bpy.ops.object.mode_set(mode='OBJECT')

material = bpy.data.materials.new("M")
material.use_nodes = True
tree = material.node_tree
node = tree.nodes.new("ShaderNodeTexImage")
node.image = loaded
to_bw = tree.nodes.new("ShaderNodeRGBToBW")
tree.links.new(node.outputs["Color"], to_bw.inputs["Color"])
tree.links.new(to_bw.outputs["Val"], tree.nodes["Principled BSDF"].inputs["Roughness"])
obj.data.materials.append(material)

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


@pytest.fixture(scope="module")
def exported_stage(tmp_path_factory) -> Path:
    workdir = tmp_path_factory.mktemp("nodedefs")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "bw.blend"
    texture = workdir / "rough.png"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), str(texture)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    stage = workdir / "out" / "bw.usda"
    stage.parent.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"),
         "export", str(blend), "-o", str(stage), "--format", "USDA"],
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, (
        "the RGB-to-BW roughness graph is ordinary and must export\n"
        + result.stdout + result.stderr
    )
    return stage


def _manifest_nodedefs() -> frozenset[str]:
    sys.path.insert(0, str(REPO_ROOT))
    sys.modules.setdefault("bpy", types.ModuleType("bpy"))
    from Plugin.manifest.materialx_nodes import load_manifest

    return frozenset(load_manifest()["nodes"].keys())


def test_every_authored_nodedef_exists_in_the_manifest(exported_stage):
    authored = set(re.findall(r'info:id = "(ND_[^"]+)"', exported_stage.read_text()))
    assert authored, "no MaterialX shaders were authored at all"

    unknown = sorted(authored - _manifest_nodedefs())
    assert unknown == [], (
        f"fabricated nodedefs shipped: {unknown}. RealityKit cannot bind a "
        "shader whose info:id exists in no MaterialX library."
    )


def test_the_colour_to_float_chain_is_the_luminance_swizzle(exported_stage):
    text = exported_stage.read_text()

    assert 'info:id = "ND_luminance_color3"' in text
    assert 'info:id = "ND_swizzle_color3_float"' in text
    assert 'inputs:channels = "r"' in text
    # And the roughness input is genuinely driven, not defaulted.
    assert re.search(r"inputs:roughness\.connect = <[^>]+>", text)
