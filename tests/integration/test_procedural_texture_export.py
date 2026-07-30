"""Integration - procedural textures must export spatially varying, warned.

Measured defect (real export, this repo, pre-fix): a Noise Texture driving
Roughness exported ok with no warning, but the authored unifiednoise3d carried
``float3 inputs:position = (0, 0, 0)`` - the unlinked Vector socket's default
folded to a constant, sampling the pattern at a single point and rendering it
flat. Voronoi additionally dropped its Scale entirely; Gradient's ramplr
texcoord was the same constant.

The contract now: the authored noise/worley shader's ``position`` (and the
ramp's ``texcoord``) input has a connection in the stage text, the export
succeeds, and an always-on warning names the deliberate approximation
(MaterialX's algorithm, object-space coordinates - bake for an exact match).
These materials are intentionally NOT in the supported-node sweep scene: the
sweep asserts zero capability warnings, and this translation warns by design.
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
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)
index = 0

def material_on_plane(name):
    global index
    bpy.ops.mesh.primitive_plane_add(location=(index * 3.0, 0, 0))
    index += 1
    obj = bpy.context.active_object
    obj.name = "Obj_" + name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    obj.data.materials.append(material)
    tree = material.node_tree
    return tree, tree.nodes["Principled BSDF"]

tree, bsdf = material_on_plane("ProceduralNoise")
noise = tree.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 7.0
tree.links.new(noise.outputs["Fac"], bsdf.inputs["Roughness"])

tree, bsdf = material_on_plane("ProceduralVoronoi")
voronoi = tree.nodes.new("ShaderNodeTexVoronoi")
voronoi.inputs["Scale"].default_value = 4.0
tree.links.new(voronoi.outputs["Distance"], bsdf.inputs["Roughness"])

tree, bsdf = material_on_plane("ProceduralGradient")
gradient = tree.nodes.new("ShaderNodeTexGradient")
tree.links.new(gradient.outputs["Fac"], bsdf.inputs["Roughness"])

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


@pytest.fixture(scope="module")
def procedural_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("procedural")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "procedural.blend"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    out_dir = workdir / "out"
    out_dir.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "--json",
         "export", str(blend), "-o", str(out_dir / "procedural.usda"),
         "--format", "USDA", "--diagnostics"],
        capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    return payload, out_dir / "procedural.usda"


def _shader_blocks(text: str):
    """Split the stage text into shader prim blocks keyed by info:id."""
    blocks = {}
    for match in re.finditer(
        r'def Shader "([^"]+)"\s*\{(.*?)\n            \}',
        text,
        re.DOTALL,
    ):
        body = match.group(2)
        id_match = re.search(r'info:id = "([^"]+)"', body)
        if id_match:
            blocks.setdefault(id_match.group(1), []).append(body)
    return blocks


def test_noise_position_is_connected_not_constant(procedural_export):
    _payload, stage = procedural_export
    blocks = _shader_blocks(stage.read_text())

    for nodedef in ("ND_unifiednoise3d_float", "ND_worleynoise3d_float"):
        assert nodedef in blocks, f"{nodedef} was not authored"
        for body in blocks[nodedef]:
            assert "inputs:position.connect" in body, (
                f"{nodedef} samples a constant position:\n{body}"
            )

    assert "ND_ramplr_float" in blocks
    for body in blocks["ND_ramplr_float"]:
        assert "inputs:texcoord.connect" in body, (
            f"ramplr samples a constant texcoord:\n{body}"
        )


def test_coordinates_come_from_object_space_position(procedural_export):
    _payload, stage = procedural_export
    text = stage.read_text()
    assert 'info:id = "ND_position_vector3"' in text
    assert 'inputs:space = "object"' in text


def test_procedural_translation_warns_by_design(procedural_export):
    payload, _stage = procedural_export
    warnings = payload.get("warnings") or []
    for material in ("ProceduralNoise", "ProceduralVoronoi", "ProceduralGradient"):
        matched = [
            warning
            for warning in warnings
            if material in warning and "pixel-for-pixel" in warning
        ]
        assert matched, f"no approximation warning for {material}: {warnings}"


def test_voronoi_scale_reaches_the_position(procedural_export):
    _payload, stage = procedural_export
    text = stage.read_text()
    # Scale 4 must survive as the combine3 feeding the position multiply.
    assert 'info:id = "ND_multiply_vector3"' in text
    voronoi_scale = re.search(
        r'info:id = "ND_combine3_vector3"[^}]*inputs:in1 = 4\b',
        text,
        re.DOTALL,
    )
    assert voronoi_scale, "Voronoi Scale did not reach the worley position"
