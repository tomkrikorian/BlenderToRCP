"""Create a disposable skinned mesh with two face materials.

Run against the checked-in Robot fixture with:

    blender References/Blender/Robot.blend --background \
      --python tests/fixtures/rcp_import/create_skinned_multimaterial_fixture.py \
      -- /tmp/RobotMultiMaterial.blend

The source file is never saved. The body material is duplicated, recolored,
and assigned to alternating faces before the modified scene is saved to the
explicit output path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy


TARGET_OBJECT = "robot_mesh_mesh_export_body_PLY"


def main(output: Path) -> None:
    target = bpy.data.objects.get(TARGET_OBJECT)
    if target is None or target.type != "MESH":
        raise RuntimeError(f"missing skinned fixture mesh: {TARGET_OBJECT}")
    if not target.data.polygons:
        raise RuntimeError(f"fixture mesh has no faces: {TARGET_OBJECT}")
    if not target.data.materials or target.data.materials[0] is None:
        raise RuntimeError(f"fixture mesh has no source material: {TARGET_OBJECT}")
    if not any(modifier.type == "ARMATURE" for modifier in target.modifiers):
        raise RuntimeError(f"fixture mesh is not armature-deformed: {TARGET_OBJECT}")

    accent = target.data.materials[0].copy()
    accent.name = "RobotBodyAccent"
    if accent.node_tree is not None:
        principled = next(
            (
                node
                for node in accent.node_tree.nodes
                if node.type == "BSDF_PRINCIPLED"
            ),
            None,
        )
        if principled is not None:
            principled.inputs["Base Color"].default_value = (
                0.02,
                0.1,
                0.8,
                1.0,
            )

    target.data.materials.append(accent)
    for polygon in target.data.polygons:
        polygon.material_index = polygon.index % 2

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == "__main__":
    separator = sys.argv.index("--")
    main(Path(sys.argv[separator + 1]))
