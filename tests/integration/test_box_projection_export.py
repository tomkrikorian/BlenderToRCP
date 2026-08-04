"""Integration - Image Texture projection BOX exports as triplanar; others refuse.

Pre-fix, every non-FLAT projection fell through the FLAT path: a Box-projected
texture silently exported as a plain UV-sampled image. Box now authors
ND_triplanarprojection_color3 with the same (staged) file on filex/filey/filez,
plus an intentional-inexactness warning; Sphere/Tube refuse the export with bake
advice. Projection Blend is not carried - see the assertion below for why.
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
import bpy, sys, os
out = sys.argv[sys.argv.index("--") + 1]
texdir = sys.argv[sys.argv.index("--") + 2]
projection = sys.argv[sys.argv.index("--") + 3]

bpy.ops.wm.read_factory_settings(use_empty=True)

path = os.path.join(texdir, "boxtex.png")
image = bpy.data.images.new("boxtex", 8, 8)
image.generated_color = (0.8, 0.4, 0.2, 1.0)
image.filepath_raw = path
image.file_format = 'PNG'
image.save()
bpy.data.images.remove(image)
loaded = bpy.data.images.load(path)

bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project()
bpy.ops.object.mode_set(mode='OBJECT')

material = bpy.data.materials.new("BoxProjected")
material.use_nodes = True
obj.data.materials.append(material)
tree = material.node_tree
bsdf = tree.nodes["Principled BSDF"]
tex = tree.nodes.new("ShaderNodeTexImage")
tex.image = loaded
tex.projection = projection
if projection == 'BOX':
    tex.projection_blend = 0.3
tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


def _build_blend(tmp_path: Path, projection: str) -> Path:
    script = tmp_path / "build.py"
    script.write_text(_BUILD)
    blend = tmp_path / f"box_{projection.lower()}.blend"
    texdir = tmp_path / "textures"
    texdir.mkdir(exist_ok=True)
    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), str(texdir), projection],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr
    return blend


def _export(blend: Path, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "--json",
         "export", str(blend), "-o", str(out_dir / "box.usda"),
         "--format", "USDA", "--diagnostics"],
        capture_output=True, text=True, timeout=900,
    )


@pytest.fixture(scope="module")
def box_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("box_projection")
    blend = _build_blend(workdir, "BOX")
    result = _export(blend, workdir / "out")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    return payload, workdir / "out" / "box.usda"


def test_box_projection_authors_triplanar(box_export):
    _payload, stage = box_export
    text = stage.read_text()
    assert 'info:id = "ND_triplanarprojection_color3"' in text

    files = {
        axis: re.search(rf'asset inputs:{axis} = @([^@]+)@', text)
        for axis in ("filex", "filey", "filez")
    }
    for axis, match in files.items():
        assert match, f"{axis} was not authored as an asset"
    # Same staged texture on every axis, relocated into the export's textures dir.
    paths = {match.group(1) for match in files.values()}
    assert len(paths) == 1, paths
    staged = paths.pop()
    assert staged.startswith("textures/"), staged
    assert (stage.parent / staged).is_file(), f"staged texture missing: {staged}"

    # Projection Blend is deliberately not carried. `blend` is a MaterialX 1.39
    # input and we declare 1.38, where RealityKit's compiler responds to an
    # undeclared input by discarding the material's whole shader graph without
    # saying so - measured with `realitytool compile`. A fixed blend width beats
    # an untextured object.
    assert "inputs:blend" not in text
    assert "inputs:upaxis" not in text


def test_box_projection_file_carries_a_color_space(box_export):
    _payload, stage = box_export
    text = stage.read_text()
    filex = re.search(
        r'asset inputs:filex = @[^@]+@ \(\s*colorSpace = "([^"]+)"', text
    )
    assert filex, "filex has no colorSpace token"
    assert filex.group(1) == "srgb_texture"


def test_box_projection_warns_about_materialx_semantics(box_export):
    payload, _stage = box_export
    warnings = payload.get("warnings") or []
    matched = [
        warning
        for warning in warnings
        if "Box projection" in warning and "pixel-for-pixel" in warning
    ]
    assert matched, f"no Box-projection warning fired: {warnings}"


def test_sphere_projection_refuses_with_bake_advice(tmp_path):
    blend = _build_blend(tmp_path, "SPHERE")
    result = _export(blend, tmp_path / "out")
    assert result.returncode != 0, (
        "SPHERE projection must refuse, not export a silently flat sample\n"
        + result.stdout
    )
    combined = result.stdout + result.stderr
    assert "SPHERE" in combined
    assert "requires baking" in combined
