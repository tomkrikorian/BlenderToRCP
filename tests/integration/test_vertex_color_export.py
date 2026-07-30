"""Integration - Color Attribute exports as a geompropvalue primvar read.

Blender 5.2's Color Attribute node (type VERTEX_COLOR) was refused outright.
Its USD exporter writes each mesh color attribute as
``primvars:<attribute name>`` (verified here against the real export), so the
exact translation is ND_geompropvalue_color3 reading the same name. The read
is only authored when the named attribute actually reaches the export: a node
naming a missing attribute refuses instead of authoring a dangling read.
"""

from __future__ import annotations

import json
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
layer_name = sys.argv[sys.argv.index("--") + 2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
mesh = obj.data
attribute = mesh.color_attributes.new(
    name="MyColors", type='BYTE_COLOR', domain='CORNER'
)
for item in attribute.data:
    item.color = (0.2, 0.5, 0.8, 1.0)

bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project()
bpy.ops.object.mode_set(mode='OBJECT')

material = bpy.data.materials.new("VertexColored")
material.use_nodes = True
obj.data.materials.append(material)
tree = material.node_tree
bsdf = tree.nodes["Principled BSDF"]
node = tree.nodes.new("ShaderNodeVertexColor")
node.layer_name = layer_name
tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


def _build_blend(tmp_path: Path, layer_name: str) -> Path:
    script = tmp_path / "build.py"
    script.write_text(_BUILD)
    blend = tmp_path / "vertex_color.blend"
    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend), layer_name],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr
    return blend


def _export(blend: Path, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "--json",
         "export", str(blend), "-o", str(out_dir / "vc.usda"),
         "--format", "USDA", "--diagnostics"],
        capture_output=True, text=True, timeout=900,
    )


@pytest.fixture(scope="module")
def vertex_color_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("vertex_color")
    blend = _build_blend(workdir, "MyColors")
    result = _export(blend, workdir / "out")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    return payload, workdir / "out" / "vc.usda"


def test_geompropvalue_reads_the_exported_primvar(vertex_color_export):
    _payload, stage = vertex_color_export
    text = stage.read_text()

    # Blender's USD exporter names the primvar after the attribute; the
    # geompropvalue read must reference exactly that name.
    assert "primvars:MyColors" in text, "mesh primvar missing from the export"
    assert 'info:id = "ND_geompropvalue_color3"' in text
    assert 'inputs:geomprop = "MyColors"' in text


def test_vertex_color_export_fires_no_capability_warning(vertex_color_export):
    payload, _stage = vertex_color_export
    noisy = [
        warning
        for warning in payload.get("warnings") or []
        if any(
            term in warning.lower()
            for term in ("unrecognized", "requires baking", "limited support")
        )
    ]
    assert noisy == [], noisy


def test_missing_attribute_refuses_instead_of_dangling(tmp_path):
    blend = _build_blend(tmp_path, "NoSuchAttribute")
    result = _export(blend, tmp_path / "out")
    assert result.returncode != 0, (
        "a Color Attribute naming a missing attribute must refuse, not author "
        "a dangling geompropvalue read\n" + result.stdout
    )
    combined = result.stdout + result.stderr
    assert "NoSuchAttribute" in combined
