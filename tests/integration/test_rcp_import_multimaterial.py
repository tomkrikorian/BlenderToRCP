"""Integration test — two-material mesh through the real RCP_IMPORT CLI lane.

Builds a cube with two materials assigned to half the faces each (Blender
exports material-binding GeomSubsets for this), runs the real
``bake-export --format RCP_IMPORT`` CLI, and asserts the generated package
carries the canonical single-descriptor multi-material representation
(docs/RCP_IMPORT_MULTI_MATERIAL_MESH.md): one mesh descriptor with a
``subsets`` array, one geometry/mesh resource/model component, and one
material record per actual material. The adjacent staged USDA must also pass
``usdchecker --arkit --strict``.
"""

from __future__ import annotations

import re
import shutil
import struct
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
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 4

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "DuoCube"
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project()
bpy.ops.object.mode_set(mode='OBJECT')

for name, color in (("RedHalf", (1.0, 0.0, 0.0, 1.0)),
                    ("BlueHalf", (0.0, 0.0, 1.0, 1.0))):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs[
        "Base Color"
    ].default_value = color
    cube.data.materials.append(material)

# Half the faces on each material -> Blender exports two materialBind
# GeomSubsets that exactly partition the six cube faces.
for index, polygon in enumerate(cube.data.polygons):
    polygon.material_index = 0 if index < 3 else 1

bpy.ops.wm.save_as_mainfile(filepath=out)
'''


def _blender() -> str:
    import os

    resolved = shutil.which(os.environ.get("BLENDERTORCP_BLENDER", "blender"))
    if resolved is None:  # pragma: no cover - guarded by the integration marker
        pytest.skip("Blender not available")
    return resolved


@pytest.fixture(scope="module")
def multimaterial_rcp_import(tmp_path_factory) -> Path:
    """Bake-export the two-material cube as RCP_IMPORT; returns the package."""

    workdir = tmp_path_factory.mktemp("rcp_import_multimaterial")
    script = workdir / "build.py"
    script.write_text(_BUILD)
    blend = workdir / "duo.blend"

    built = subprocess.run(
        [_blender(), "--background", "--factory-startup", "--python", str(script),
         "--", str(blend)],
        capture_output=True, text=True, timeout=300,
    )
    assert blend.exists(), built.stdout + built.stderr

    out_dir = workdir / "out"
    out_dir.mkdir()
    exported = subprocess.run(
        [sys.executable, str(REPO_ROOT / "Plugin"), "bake-export", str(blend),
         "-o", str(out_dir / "DuoCube.import"), "--format", "RCP_IMPORT",
         "--bake-mode", "UNLIT_ALBEDO", "--resolution", "64"],
        capture_output=True, text=True, timeout=900,
    )
    assert exported.returncode == 0, exported.stdout + exported.stderr
    package = out_dir / "DuoCube.import"
    assert package.is_dir(), exported.stdout + exported.stderr
    return package


def test_package_inspects_clean_with_canonical_subsets(multimaterial_rcp_import):
    from scripts._lib.rcp_import_contract import build_report, inspect_import

    inspection = inspect_import(multimaterial_rcp_import)
    assert inspection.errors == []
    report = build_report(inspection, rcp_build="80.0.1.500.1")
    # One mesh: one geometry, one descriptor, one mesh resource; one material
    # record per actual material. (Flat Principled colors classify as flat
    # bake results, so no texture records are required here.)
    assert report["record_types"]["tm_geometry"] == 1
    assert report["record_types"]["tm_mesh_descriptor"] == 1
    assert report["record_types"]["tm_mesh_resource"] == 1
    assert report["record_types"]["tm_material"] == 2
    assert report["counts"]["derived_or_unknown_hashed_buffers"] == 0


def test_descriptor_carries_exhaustive_subset_partition(multimaterial_rcp_import):
    descriptor_path = next(
        (multimaterial_rcp_import / "mesh_descriptors").glob("*.tm_mesh_descriptor")
    )
    descriptor = descriptor_path.read_text()
    subsets = re.search(r"\nsubsets: \[\n(.*?)\n\]\n", descriptor, re.S)
    assert subsets is not None
    names = re.findall(r'name: "([^"]+)"', subsets.group(1))
    assert len(names) == 2
    assert all(name.startswith("/") for name in names), (
        "subset names must be full USD GeomSubset prim paths"
    )
    assert "material_bindings" not in descriptor

    # The two face-index buffers must partition all six cube faces.
    buffer_ids = re.findall(r'face_indices: "([0-9a-f-]{36})"', descriptor)
    buffer_dir = descriptor_path.parent / f"{descriptor_path.stem}.tm_buffers"
    faces: list[set[int]] = []
    for buffer_id in buffer_ids:
        payload = next(buffer_dir.glob(f"{buffer_id}.*")).read_bytes()
        faces.append(
            set(struct.unpack(f"<{len(payload) // 4}I", payload))
        )
    assert faces[0].isdisjoint(faces[1])
    assert faces[0] | faces[1] == set(range(6))


def test_adjacent_usda_passes_arkit_strict_usdchecker(multimaterial_rcp_import):
    usda = multimaterial_rcp_import.parent / "DuoCube.usda"
    assert usda.is_file(), "RCP_IMPORT must publish the adjacent staged USDA"
    usdchecker = shutil.which("usdchecker") or "/usr/bin/usdchecker"
    if not Path(usdchecker).exists():
        pytest.skip("usdchecker not available")
    checked = subprocess.run(
        [usdchecker, "--arkit", "--strict", str(usda)],
        capture_output=True, text=True, timeout=300,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
