"""Integration test — the four-channel reader follows the file, not the wish.

Reality Composer Pro 3.0 replaces a material with a striped placeholder when a
four-channel vector reader appears, so every read is authored as color3 or
color4. Choosing between them is the one place the source file's real channel
count is load-bearing: a consumer asking for alpha over a three-channel PNG
used to author a four-channel read of a file with only three.

Two materials, one export:

* ``AlphaSprite`` — RGBA base color whose Alpha drives Principled Alpha.
  Authors ``ND_image_color4`` + ``ND_separate4_color4`` into ``inputs:opacity``.
* ``NoAlphaSprite`` — RGB base color wired the same way. The read is refused,
  a warning names the file and the input, and opacity keeps its default.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

_BUILD = r'''
import bpy, os, sys
out = sys.argv[sys.argv.index("--") + 1]
texdir = sys.argv[sys.argv.index("--") + 2]

bpy.ops.wm.read_factory_settings(use_empty=True)


def make(name, alpha):
    path = os.path.join(texdir, name + ".png")
    image = bpy.data.images.new(name, 8, 8, alpha=alpha)
    image.generated_color = (0.8, 0.2, 0.2, 0.5)
    image.filepath_raw = path
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)
    return bpy.data.images.load(path)


index = 0


def material(name, image):
    global index
    bpy.ops.mesh.primitive_plane_add(location=(index * 3.0, 0, 0))
    index += 1
    obj = bpy.context.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    obj.data.materials.append(mat)
    tree = mat.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])


material("AlphaSprite", make("sprite_rgba", True))
material("NoAlphaSprite", make("sprite_rgb", False))

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


@pytest.fixture(scope="module")
def alpha_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("alpha_reader")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "alpha.blend"
    texdir = workdir / "textures"
    texdir.mkdir()

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), str(texdir)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    out_dir = workdir / "out"
    out_dir.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "--json",
         "export", str(blend), "-o", str(out_dir / "alpha.usda"),
         "--format", "USDA"],
        capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout), out_dir / "alpha.usda"


def _material_block(text: str, name: str) -> str:
    start = text.index(f'def Material "{name}"')
    following = [
        match.start()
        for match in re.finditer(r'\n {8}def Material "', text)
        if match.start() > start
    ]
    return text[start:following[0]] if following else text[start:]


def test_alpha_over_an_rgba_source_uses_color4_and_separate4(alpha_export):
    _payload, stage = alpha_export
    block = _material_block(stage.read_text(), "AlphaSprite")

    assert 'info:id = "ND_image_color4"' in block
    assert 'info:id = "ND_separate4_color4"' in block
    assert re.search(r"inputs:opacity\.connect = <[^>]+separate4\.outputs:outa>", block)


def test_alpha_over_an_rgb_source_is_refused_with_a_warning(alpha_export):
    payload, stage = alpha_export
    block = _material_block(stage.read_text(), "NoAlphaSprite")

    assert 'info:id = "ND_image_color4"' not in block
    # The retained UsdPreviewSurface network still reads its own alpha; only
    # the MaterialX surface must fall back to the default.
    assert "separate4" not in block
    assert re.search(r"inputs:opacity = 1\b", block)

    warnings = payload.get("warnings") or []
    named = [
        warning
        for warning in warnings
        # The path may be a staged snapshot, so match the stem, not the file.
        if "sprite_rgb" in warning and "no alpha channel" in warning
    ]
    assert named, f"the refusal was silent: {warnings}"


def test_no_four_channel_vector_reader_ships(alpha_export):
    _payload, stage = alpha_export
    text = stage.read_text()

    for nodedef in (
        "ND_image_vector4",
        "ND_swizzle_vector4_float",
        "ND_extract_vector4",
        "ND_separate4_vector4",
    ):
        assert f'info:id = "{nodedef}"' not in text
