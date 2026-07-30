"""Integration test — supported node types export from real Blender, silently.

22 of the validator's 29 supported node types had zero real-Blender coverage:
they were exercised only through SimpleNamespace doubles, and the graphs the
suite actually exported end-to-end were a factory Principled plus one image on
Base Color. That gap is where the silent-translation defects lived — measured,
a plain ``Value -> Clamp -> Roughness`` graph exported successfully while
emitting "Node 'Clamp' (CLAMP) is unrecognized; export may differ", because the
warning table had drifted 14 entries behind the validator.

One scene, one object+material per node type in its minimal resolvable
configuration, one export. The contract: every material converts, and no
capability warning ("unrecognized", "requires baking", "limited support")
fires for any of them. This is the behavioural test the source-introspecting
capability-parity test could not be.
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

#: Node types deliberately absent, with the measured reason:
#: GAMMA/COMBXYZ/CURVE_* etc. are BAKE_TYPES by policy; MATH operations
#: outside validate.SUPPORTED_MATH_OPERATIONS are refused (covered by the
#: refusal fixture below); TEX_COORD/UVMAP/MAPPING are PARTIAL_TYPES that
#: warn by design; BRIGHTCONTRAST on colour is a recorded open defect (type
#: mismatch).
_BUILD = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]
texdir = sys.argv[sys.argv.index("--") + 2]

bpy.ops.wm.read_factory_settings(use_empty=True)

def make_image(name, color, non_color=False):
    import os
    path = os.path.join(texdir, name + ".png")
    image = bpy.data.images.new(name, 8, 8)
    image.generated_color = color
    image.filepath_raw = path
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)
    loaded = bpy.data.images.load(path)
    if non_color:
        loaded.colorspace_settings.name = 'Non-Color'
    return loaded

albedo = make_image("albedo", (0.8, 0.2, 0.2, 1.0))
detail = make_image("detail", (0.2, 0.6, 0.9, 1.0))
data_map = make_image("data_map", (0.5, 0.5, 0.5, 1.0), non_color=True)
normal_map = make_image("normal_map", (0.5, 0.5, 1.0, 1.0), non_color=True)

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

# TEX_IMAGE
tree, bsdf = material_on_plane("SweepTexImage")
node = tree.nodes.new("ShaderNodeTexImage"); node.image = albedo
tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])

# RGB
tree, bsdf = material_on_plane("SweepRGB")
node = tree.nodes.new("ShaderNodeRGB")
node.outputs[0].default_value = (0.1, 0.7, 0.3, 1.0)
tree.links.new(node.outputs[0], bsdf.inputs["Base Color"])

# VALUE
tree, bsdf = material_on_plane("SweepValue")
node = tree.nodes.new("ShaderNodeValue")
node.outputs[0].default_value = 0.35
tree.links.new(node.outputs[0], bsdf.inputs["Roughness"])

# CLAMP
tree, bsdf = material_on_plane("SweepClamp")
value = tree.nodes.new("ShaderNodeValue"); value.outputs[0].default_value = 0.7
clamp = tree.nodes.new("ShaderNodeClamp")
tree.links.new(value.outputs[0], clamp.inputs["Value"])
tree.links.new(clamp.outputs[0], bsdf.inputs["Roughness"])

# MAP_RANGE
tree, bsdf = material_on_plane("SweepMapRange")
value = tree.nodes.new("ShaderNodeValue"); value.outputs[0].default_value = 0.4
map_range = tree.nodes.new("ShaderNodeMapRange")
tree.links.new(value.outputs[0], map_range.inputs["Value"])
tree.links.new(map_range.outputs["Result"], bsdf.inputs["Roughness"])

# INVERT
tree, bsdf = material_on_plane("SweepInvert")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = data_map
invert = tree.nodes.new("ShaderNodeInvert")
tree.links.new(tex.outputs["Color"], invert.inputs["Color"])
tree.links.new(invert.outputs["Color"], bsdf.inputs["Roughness"])

# RGBTOBW
tree, bsdf = material_on_plane("SweepRGBToBW")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = data_map
to_bw = tree.nodes.new("ShaderNodeRGBToBW")
tree.links.new(tex.outputs["Color"], to_bw.inputs["Color"])
tree.links.new(to_bw.outputs["Val"], bsdf.inputs["Roughness"])

# SEPARATE_COLOR (the packed-ORM idiom)
tree, bsdf = material_on_plane("SweepSeparate")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = data_map
separate = tree.nodes.new("ShaderNodeSeparateColor")
tree.links.new(tex.outputs["Color"], separate.inputs["Color"])
tree.links.new(separate.outputs["Green"], bsdf.inputs["Roughness"])
tree.links.new(separate.outputs["Blue"], bsdf.inputs["Metallic"])

# VALTORGB (Color Ramp, default two stops)
tree, bsdf = material_on_plane("SweepRamp")
value = tree.nodes.new("ShaderNodeValue"); value.outputs[0].default_value = 0.6
ramp = tree.nodes.new("ShaderNodeValToRGB")
tree.links.new(value.outputs[0], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

# HUE_SAT
tree, bsdf = material_on_plane("SweepHueSat")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = albedo
hue = tree.nodes.new("ShaderNodeHueSaturation")
tree.links.new(tex.outputs["Color"], hue.inputs["Color"])
tree.links.new(hue.outputs["Color"], bsdf.inputs["Base Color"])

# MIX (RGBA multiply, both inputs linked - the AO-times-albedo idiom)
tree, bsdf = material_on_plane("SweepMix")
tex_a = tree.nodes.new("ShaderNodeTexImage"); tex_a.image = albedo
tex_b = tree.nodes.new("ShaderNodeTexImage"); tex_b.image = detail
mix = tree.nodes.new("ShaderNodeMix")
mix.data_type = 'RGBA'
mix.blend_type = 'MULTIPLY'
mix.inputs["Factor"].default_value = 1.0
tree.links.new(tex_a.outputs["Color"], mix.inputs[6])
tree.links.new(tex_b.outputs["Color"], mix.inputs[7])
tree.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

# NORMAL_MAP
tree, bsdf = material_on_plane("SweepNormal")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = normal_map
normal = tree.nodes.new("ShaderNodeNormalMap")
tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])

# MATH (roughness x 0.8 - the motivating non-identity case)
tree, bsdf = material_on_plane("SweepMathMultiply")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = data_map
math_node = tree.nodes.new("ShaderNodeMath")
math_node.operation = 'MULTIPLY'
math_node.inputs[1].default_value = 0.8
tree.links.new(tex.outputs["Color"], math_node.inputs[0])
tree.links.new(math_node.outputs["Value"], bsdf.inputs["Roughness"])

# MATH composed: MULTIPLY_ADD (multiply + add nodes) with use_clamp (clamp)
tree, bsdf = material_on_plane("SweepMathMultiplyAdd")
tex = tree.nodes.new("ShaderNodeTexImage"); tex.image = data_map
math_node = tree.nodes.new("ShaderNodeMath")
math_node.operation = 'MULTIPLY_ADD'
math_node.use_clamp = True
math_node.inputs[1].default_value = 0.5
math_node.inputs[2].default_value = 0.25
tree.links.new(tex.outputs["Color"], math_node.inputs[0])
tree.links.new(math_node.outputs["Value"], bsdf.inputs["Roughness"])

# EMISSION as the active surface
tree, _bsdf = material_on_plane("SweepEmission")
emission = tree.nodes.new("ShaderNodeEmission")
emission.inputs["Color"].default_value = (1.0, 0.5, 0.1, 1.0)
output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL')
tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])

bpy.ops.wm.save_as_mainfile(filepath=out)
print("SWEEP_MATERIALS:", len(bpy.data.materials))
'''

_SWEEP_MATERIALS = [
    "SweepTexImage", "SweepRGB", "SweepValue", "SweepClamp", "SweepMapRange",
    "SweepInvert", "SweepRGBToBW", "SweepSeparate", "SweepRamp", "SweepHueSat",
    "SweepMix", "SweepNormal", "SweepMathMultiply", "SweepMathMultiplyAdd",
    "SweepEmission",
]

_CAPABILITY_NOISE = ("unrecognized", "requires baking", "limited support")


def _blender() -> str:
    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


@pytest.fixture(scope="module")
def sweep_export(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("sweep")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "sweep.blend"
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
         "export", str(blend), "-o", str(out_dir / "sweep.usda"),
         "--format", "USDA", "--diagnostics"],
        capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, (
        "every material in the sweep uses only validator-supported nodes in a "
        "resolvable configuration; the export must succeed\n"
        + result.stdout + result.stderr
    )
    payload = json.loads(result.stdout)
    return payload, out_dir / "sweep.usda"


def test_every_sweep_material_is_authored(sweep_export):
    _payload, stage = sweep_export
    text = stage.read_text()

    missing = [name for name in _SWEEP_MATERIALS if f'"{name}"' not in text]
    assert missing == [], f"materials dropped from the export: {missing}"


def test_no_capability_warning_fires_for_supported_nodes(sweep_export):
    """The property the drifted warning table violated: a supported node must
    not be described as unrecognized or bake-only."""
    payload, _stage = sweep_export

    noisy = [
        warning
        for warning in payload.get("warnings") or []
        if any(term in warning.lower() for term in _CAPABILITY_NOISE)
    ]
    assert noisy == [], (
        "capability warnings fired for validator-supported node types: "
        f"{noisy}"
    )


def test_no_unmapped_color_space_token_ships(sweep_export):
    """RCP 3.0 (80.0.1.500.1) has no alias for Blender's OCIO name
    ``srgb_rec709_display``; the postprocess renames it to ``srgb_texture``.
    A surviving occurrence means the retag step regressed."""
    _payload, stage = sweep_export

    assert "srgb_rec709_display" not in stage.read_text()


def test_math_materials_author_real_materialx_nodes(sweep_export):
    """roughness x 0.8 must ship as a real multiply, and the composed
    MULTIPLY_ADD with use_clamp must ship multiply + add + clamp."""
    _payload, stage = sweep_export
    text = stage.read_text()

    for nodedef in ("ND_multiply_float", "ND_add_float", "ND_clamp_float"):
        assert f'info:id = "{nodedef}"' in text, f"{nodedef} was not authored"


def test_every_authored_nodedef_is_manifest_backed(sweep_export):
    """The sweep doubles as a broad corpus for the nodedef closing gate."""
    import re
    import types

    _payload, stage = sweep_export
    sys.path.insert(0, str(REPO_ROOT))
    sys.modules.setdefault("bpy", types.ModuleType("bpy"))
    from Plugin.manifest.materialx_nodes import load_manifest

    known = frozenset(load_manifest()["nodes"].keys())
    authored = set(re.findall(r'info:id = "(ND_[^"]+)"', stage.read_text()))
    assert authored, "no MaterialX shaders authored"

    unknown = sorted(authored - known)
    assert unknown == [], f"fabricated nodedefs shipped: {unknown}"


# --- refusal control: unsupported Math operations keep the bake advice ------

_REFUSED_BUILD = r'''
import bpy, sys
out = sys.argv[sys.argv.index("--") + 1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add()
obj = bpy.context.active_object
material = bpy.data.materials.new("RefusedMathSmoothMin")
material.use_nodes = True
obj.data.materials.append(material)
tree = material.node_tree
bsdf = tree.nodes["Principled BSDF"]

value = tree.nodes.new("ShaderNodeValue"); value.outputs[0].default_value = 0.4
math_node = tree.nodes.new("ShaderNodeMath")
math_node.operation = 'SMOOTH_MIN'
math_node.inputs[1].default_value = 0.3
tree.links.new(value.outputs[0], math_node.inputs[0])
tree.links.new(math_node.outputs["Value"], bsdf.inputs["Roughness"])

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


@pytest.fixture(scope="module")
def refused_math_blend(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("refused_math")
    script = workdir / "build.py"
    script.write_text(_REFUSED_BUILD)
    blend = workdir / "refused.blend"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr
    return blend


def test_unsupported_math_operation_still_refuses_with_bake_advice(refused_math_blend):
    """SMOOTH_MIN has no exact MaterialX equivalent; the validator must name
    the operation and keep the bake advice - never approximate silently."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "--json",
         "validate", str(refused_math_blend)],
        capture_output=True, text=True, timeout=900,
    )
    payload = json.loads(result.stdout)

    entry = next(
        material for material in payload["materials"]
        if material["name"] == "RefusedMathSmoothMin"
    )
    assert entry["ok"] is False
    messages = [issue["message"] for issue in entry["errors"]]
    refusals = [m for m in messages if "SMOOTH_MIN" in m]
    assert refusals, f"no refusal names the operation: {messages}"
    assert any("requires baking" in m for m in refusals)
