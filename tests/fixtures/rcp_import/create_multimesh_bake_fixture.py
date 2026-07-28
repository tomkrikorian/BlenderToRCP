"""Create the disposable multi-mesh/material Blender acceptance fixture.

Run with:

    blender --background --factory-startup \
      --python tests/fixtures/rcp_import/create_multimesh_bake_fixture.py \
      -- /tmp/MultiMeshMaterials.blend

Append ``--flat`` after the output path for a direct-export-compatible variant
that keeps the same three-object/two-material/material-subset topology.
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


def _material(
    name: str,
    color: tuple[float, float, float, float],
    scale: float,
    *,
    procedural: bool,
):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    principled.inputs["Base Color"].default_value = color
    if not procedural:
        principled.inputs["Roughness"].default_value = 0.5
        return material
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 3.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.01, 0.01, 0.01, 1.0)
    ramp.color_ramp.elements[1].color = color
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(noise.outputs["Fac"], principled.inputs["Roughness"])
    return material


def _cube(name: str, location: tuple[float, float, float]):
    bpy.ops.mesh.primitive_cube_add(location=location)
    cube = bpy.context.object
    cube.name = name
    cube.data.name = f"{name}Mesh"
    return cube


def main(output: Path, *, procedural: bool = True) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    red = _material(
        "ProceduralRed" if procedural else "FlatRed",
        (0.8, 0.01, 0.01, 1.0),
        3.0,
        procedural=procedural,
    )
    blue = _material(
        "ProceduralBlue" if procedural else "FlatBlue",
        (0.01, 0.03, 0.8, 1.0),
        7.0,
        procedural=procedural,
    )

    left = _cube("Left", (-1.5, 0.0, 0.0))
    left.data.materials.append(red)

    right = _cube("Right", (1.5, 0.0, 0.0))
    right.data.materials.append(blue)

    split = _cube("Split", (0.0, 0.0, 2.5))
    split.data.materials.append(red)
    split.data.materials.append(blue)
    for polygon in split.data.polygons:
        polygon.material_index = polygon.index % 2

    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.world.color = (0.05, 0.05, 0.05)
    bpy.ops.wm.save_as_mainfile(filepath=str(output.resolve()))


if __name__ == "__main__":
    separator = sys.argv.index("--")
    arguments = sys.argv[separator + 1 :]
    main(Path(arguments[0]), procedural="--flat" not in arguments[1:])
