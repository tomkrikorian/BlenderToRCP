"""Integration test — a Non-Color image on Base Color is exportable.

The exporter emits two networks per material: the MaterialX ShaderGraph that
RealityKit consumes, and the native UsdPreviewSurface network Blender authored,
kept for other USD consumers such as Quick Look.

``textures._materialx_file_colorspace`` decides that a Blender Non-Color image
feeding a perceptual colour input is scene-linear and authors ``lin_rec709``.
Blender tags its own copy of that same file ``data`` through ColorSpaceAPI, so
the two networks disagreed about one image and preflight - which inspects the
whole stage - rejected the export with TEXTURE_COLOR_SPACE_MISMATCH on the
preview network's texture.

The material is legal, ``validate`` reports it OK, the MaterialX graph is
correct, and nothing the user could change in Blender would fix it. Real
scenario: pre-linearized albedo, an EXR, or a UI atlas.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

_BUILD = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
texture = sys.argv[sys.argv.index("--") + 2]
colorspace = sys.argv[sys.argv.index("--") + 3]

bpy.ops.wm.read_factory_settings(use_empty=True)

image = bpy.data.images.new("albedo", 8, 8)
image.generated_color = (0.8, 0.2, 0.2, 1.0)
image.filepath_raw = texture
image.file_format = 'PNG'
image.save()
bpy.data.images.remove(image)

loaded = bpy.data.images.load(texture)
loaded.colorspace_settings.name = colorspace

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
tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
obj.data.materials.append(material)

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


def _export_scene(tmp_path: Path, colorspace: str):
    script = tmp_path / f"build_{colorspace.replace('-', '_')}.py"
    script.write_text(_BUILD)
    blend = tmp_path / f"{colorspace.replace('-', '_')}.blend"
    texture = tmp_path / f"{colorspace.replace('-', '_')}.png"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), str(texture), colorspace],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    out_dir = tmp_path / f"out_{colorspace.replace('-', '_')}"
    out_dir.mkdir()
    stage = out_dir / "s.usda"
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "export", str(blend),
         "-o", str(stage), "--format", "USDA"],
        capture_output=True, text=True, timeout=600,
    )
    return result, stage


def test_non_color_base_color_exports(tmp_path):
    result, stage = _export_scene(tmp_path, "Non-Color")

    assert result.returncode == 0, (
        "a Non-Color image on Base Color is a legal material that validate "
        "accepts; the export must not reject it\n" + result.stdout + result.stderr
    )
    assert stage.exists()
    text = stage.read_text()
    assert 'colorSpace = "lin_rec709"' in text, (
        "the retained preview network must agree with the MaterialX graph"
    )


def test_srgb_base_color_is_left_alone(tmp_path):
    """The normalisation must fire only for data-space colour textures."""
    result, stage = _export_scene(tmp_path, "sRGB")

    assert result.returncode == 0, result.stdout + result.stderr
    text = stage.read_text()
    assert 'colorSpace = "srgb_texture"' in text
    assert 'colorSpace = "lin_rec709"' not in text, (
        "an sRGB texture was retagged; the rule is too broad"
    )
