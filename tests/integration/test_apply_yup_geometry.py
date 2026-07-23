"""Integration test — ``bake_finalize.apply_yup_geometry_bake``.

Regression coverage for the instancing-safe Y-up geometry bake (commit
62f45d8). The function under test calls ``bpy``/``mathutils`` directly
(``mesh.transform``, ``matrix_world`` parent inheritance, depsgraph updates),
so faking ``bpy`` would not exercise the behavior that actually regressed.
This test therefore runs the real assertions *inside* Blender.

Mirroring the project's CLI bridge (``Plugin/cli/bridge.py``), it spawns
``blender --background --factory-startup --python <driver> -- <markers>`` and
parses a JSON result delimited by a unique marker out of Blender's noisy
stdout. Each scenario asserts inside Blender and reports pass/fail back; the
pytest layer surfaces per-scenario detail on failure.

The driver builds throwaway cube meshes via ``bmesh`` in a scratch scene and
never touches any user .blend file.

Run it with::

    pytest tests/integration/test_apply_yup_geometry.py

Blender is located via ``$BLENDERTORCP_BLENDER`` (else ``blender`` on PATH),
the same lookup the bridge and conftest use; the whole module auto-skips when
Blender is unavailable (see ``tests/conftest.py``).
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


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_PARENT = str(REPO_ROOT)  # so ``from Plugin.export import bake_finalize`` resolves

# Unique so it can't collide with Blender's startup chatter.
OUTPUT_MARKER = "---YUP_GEOMETRY_TEST_JSON---"


def _find_blender() -> str:
    return os.environ.get("BLENDERTORCP_BLENDER", "blender")


# ---------------------------------------------------------------------------
# In-Blender driver
# ---------------------------------------------------------------------------
#
# Executed by ``blender --background --python``. It constructs scenes, runs
# ``apply_yup_geometry_bake``, asserts the six guarantees, and prints a JSON
# report between markers. Kept as a string (not an importable module) so the
# whole test lives in one file and runs only inside Blender's interpreter.

DRIVER_SOURCE = r'''
import json
import math
import sys
import traceback

import bpy
import bmesh
from mathutils import Matrix, Vector

PLUGIN_PARENT = sys.argv[sys.argv.index("--") + 1]
OUTPUT_MARKER = sys.argv[sys.argv.index("--") + 2]

if PLUGIN_PARENT not in sys.path:
    sys.path.insert(0, PLUGIN_PARENT)

from Plugin.export import bake_finalize  # noqa: E402

# The orientation rotation the function bakes in (must match the source).
Rg = Matrix.Rotation(math.radians(-90), 4, "X")
TOL = 1e-5


class _Settings:
    """Minimal stand-in for the real settings object — only needs a mutable
    ``convert_orientation`` attribute, per the function contract."""

    def __init__(self):
        self.convert_orientation = True


def _new_scene(name):
    """Fresh scratch scene linked to a fresh view layer context."""
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    return scene


def _make_cube_mesh(name):
    """A unit-ish cube mesh datablock built with bmesh (no ops, no defaults)."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def _link(scene, name, mesh):
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def _world_pts(obj):
    """World-space coordinates of every vertex of an object's evaluated-free
    local mesh (we read the raw mesh verts; matrix_world carries placement)."""
    mw = obj.matrix_world
    return [mw @ v.co.copy() for v in obj.data.vertices]


def _local_pts(mesh):
    return [v.co.copy() for v in mesh.vertices]


def _close(a, b, tol=TOL):
    return (a - b).length <= tol


def _matrix_delta(a, b):
    return max(abs(a[row][col] - b[row][col]) for row in range(4) for col in range(4))


def _all_world_rotated(new_obj, old_world_pts):
    """Assert new world geometry == Rg @ old world geometry, vertex by vertex."""
    new = _world_pts(new_obj)
    if len(new) != len(old_world_pts):
        return False, "vertex count changed"
    worst = 0.0
    for n, o in zip(new, old_world_pts):
        d = (n - (Rg @ o)).length
        worst = max(worst, d)
    return worst <= TOL, "max world delta = %g" % worst


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def scenario_instancing_preserved():
    """Two objects share one mesh; full-scene scope.

    The shared mesh is rotated exactly once and stays shared: both objects
    still point at the same datablock, the user count is unchanged, and no
    extra mesh copies were created.
    """
    scene = _new_scene("instancing")
    mesh = _make_cube_mesh("shared")
    a = _link(scene, "inst_a", mesh)
    b = _link(scene, "inst_b", mesh)
    a.location = (3.0, 0.0, 0.0)
    b.location = (-3.0, 1.0, 2.0)
    a.rotation_euler = (0.3, 0.2, 0.1)
    bpy.context.view_layer.update()

    users_before = mesh.users
    mesh_count_before = len(bpy.data.meshes)
    old_a = _world_pts(a)
    old_b = _world_pts(b)

    bake_finalize.apply_yup_geometry_bake(bpy.context, _Settings(), objects=None)

    ok_share = (a.data is mesh and b.data is mesh)
    ok_users = (mesh.users == users_before)
    ok_nocopy = (len(bpy.data.meshes) == mesh_count_before)
    ok_a, det_a = _all_world_rotated(a, old_a)
    ok_b, det_b = _all_world_rotated(b, old_b)

    ok = ok_share and ok_users and ok_nocopy and ok_a and ok_b
    detail = (
        "shared=%s users(%d->%d) nocopy=%s a:%s b:%s"
        % (ok_share, users_before, mesh.users, ok_nocopy, det_a, det_b)
    )
    return ok, detail


def scenario_world_preserving():
    """A lone object with rotation + non-uniform scale: world geometry must
    equal Rg @ old world geometry exactly."""
    scene = _new_scene("world")
    mesh = _make_cube_mesh("solo")
    obj = _link(scene, "solo", mesh)
    obj.location = (1.5, -2.0, 4.0)
    obj.rotation_euler = (0.5, -0.4, 0.9)
    obj.scale = (2.0, 0.5, 1.3)
    bpy.context.view_layer.update()

    old = _world_pts(obj)
    bake_finalize.apply_yup_geometry_bake(bpy.context, _Settings(), objects=None)
    ok, det = _all_world_rotated(obj, old)
    return ok, det


def scenario_parented_child():
    """The regression: parent with rotation + non-uniform scale, plus a
    parented child. After the bake the CHILD's world geometry must also equal
    Rg @ old. (Pre-fix the child was mis-placed by ~6 units.)"""
    scene = _new_scene("parented")
    parent_mesh = _make_cube_mesh("parent_mesh")
    child_mesh = _make_cube_mesh("child_mesh")
    parent = _link(scene, "parent", parent_mesh)
    child = _link(scene, "child", child_mesh)

    parent.location = (2.0, 1.0, 0.5)
    parent.rotation_euler = (0.6, 0.2, -0.3)
    parent.scale = (1.7, 0.6, 2.2)  # non-uniform on purpose
    bpy.context.view_layer.update()

    # Parent the child while keeping its current world transform.
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.location = (1.0, 2.0, 3.0)
    bpy.context.view_layer.update()

    old_parent = _world_pts(parent)
    old_child = _world_pts(child)

    bake_finalize.apply_yup_geometry_bake(bpy.context, _Settings(), objects=None)

    ok_p, det_p = _all_world_rotated(parent, old_parent)
    ok_c, det_c = _all_world_rotated(child, old_child)
    return (ok_p and ok_c), "parent:%s child:%s" % (det_p, det_c)


def scenario_shape_keys():
    """A mesh with shape keys: its shape-key coordinates rotate with the base
    mesh (the call passes shape_keys=True). We compare a sampled shape-key
    vertex before/after against Rg @ old (object at identity transform)."""
    scene = _new_scene("shapekeys")
    mesh = _make_cube_mesh("keyed")
    obj = _link(scene, "keyed", mesh)
    bpy.context.view_layer.update()

    # Basis + one deformed key. Object stays at identity so local == world,
    # isolating the mesh-datablock transform.
    bpy.context.view_layer.objects.active = obj
    basis = obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="Deform", from_mix=False)
    # Nudge the deformed key so it is clearly distinct from basis.
    for i in range(len(key.data)):
        key.data[i].co = key.data[i].co + Vector((0.0, 0.0, 0.5))

    old_basis = [p.co.copy() for p in basis.data]
    old_key = [p.co.copy() for p in key.data]

    bake_finalize.apply_yup_geometry_bake(bpy.context, _Settings(), objects=None)

    worst = 0.0
    for kd, o in zip(key.data, old_key):
        worst = max(worst, (kd.co - (Rg @ o)).length)
    for bd, o in zip(basis.data, old_basis):
        worst = max(worst, (bd.co - (Rg @ o)).length)
    ok = worst <= TOL
    return ok, "max shape-key delta = %g" % worst


def scenario_scope_guard():
    """A mesh shared by an in-scope and an out-of-scope object. Only the
    in-scope object is passed. Because not all users are in scope, the mesh
    must NOT be baked in place (its local verts unchanged); the in-scope
    object instead rotates via its transform, and the out-of-scope object is
    untouched entirely."""
    scene = _new_scene("scope")
    mesh = _make_cube_mesh("partly_shared")
    inside = _link(scene, "inside", mesh)
    outside = _link(scene, "outside", mesh)
    inside.location = (4.0, 0.0, 0.0)
    outside.location = (-4.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    old_local = _local_pts(mesh)
    old_inside_world = _world_pts(inside)
    old_outside_world = _world_pts(outside)
    users_before = mesh.users

    # Restrict scope to the in-scope object only.
    bake_finalize.apply_yup_geometry_bake(bpy.context, _Settings(), objects=[inside])

    new_local = _local_pts(mesh)
    mesh_unchanged = all(_close(a, b) for a, b in zip(old_local, new_local))

    # In-scope object rotated via transform -> world is Rg @ old.
    ok_inside, det_inside = _all_world_rotated(inside, old_inside_world)

    # Out-of-scope object untouched: same world geometry as before.
    new_outside_world = _world_pts(outside)
    outside_unchanged = all(
        _close(a, b) for a, b in zip(old_outside_world, new_outside_world)
    )

    # Instancing preserved (still shared, no copy/split).
    still_shared = (inside.data is mesh and outside.data is mesh)
    ok_users = mesh.users == users_before

    ok = mesh_unchanged and ok_inside and outside_unchanged and still_shared and ok_users
    detail = (
        "mesh_unchanged=%s inside(%s) outside_unchanged=%s shared=%s users(%d->%d)"
        % (mesh_unchanged, det_inside, outside_unchanged, still_shared,
           users_before, mesh.users)
    )
    return ok, detail


def scenario_convert_orientation_disabled():
    """``settings.convert_orientation`` must be False after the call."""
    scene = _new_scene("flag")
    mesh = _make_cube_mesh("flag_cube")
    _link(scene, "flag_cube", mesh)
    bpy.context.view_layer.update()

    settings = _Settings()
    settings.convert_orientation = True
    bake_finalize.apply_yup_geometry_bake(bpy.context, settings, objects=None)
    ok = settings.convert_orientation is False
    return ok, "convert_orientation=%r" % (settings.convert_orientation,)


def _scenario_transactional_failure(helper_name, use_delta=False):
    """Force a failure *after* one mutation and require an exact rollback."""
    scene = _new_scene("transaction_" + helper_name)
    mesh = _make_cube_mesh("transaction_mesh_" + helper_name)
    obj = _link(scene, "transaction_obj_" + helper_name, mesh)
    obj.location = (1.25, -2.5, 3.75)
    obj.rotation_euler = (0.2, -0.4, 0.6)
    obj.scale = (1.2, 0.8, 1.5)
    if use_delta:
        # Delta transforms take the matrix_world fallback path.
        obj.delta_location = (0.25, 0.0, 0.0)
    bpy.context.view_layer.update()

    old_local = _local_pts(mesh)
    old_basis = obj.matrix_basis.copy()
    old_parent_inverse = obj.matrix_parent_inverse.copy()
    old_world = obj.matrix_world.copy()
    settings = _Settings()

    original = getattr(bake_finalize, helper_name)
    called = {"failed": False}

    def fail_after_mutation(*args):
        original(*args)
        if not called["failed"]:
            called["failed"] = True
            raise RuntimeError("forced transactional rewrite failure")

    setattr(bake_finalize, helper_name, fail_after_mutation)
    raised = False
    error = ""
    try:
        bake_finalize.apply_yup_geometry_bake(
            bpy.context,
            settings,
            objects=None,
        )
    except RuntimeError as exc:
        raised = True
        error = str(exc)
    finally:
        setattr(bake_finalize, helper_name, original)

    new_local = _local_pts(mesh)
    mesh_restored = all(_close(a, b) for a, b in zip(old_local, new_local))
    basis_delta = _matrix_delta(obj.matrix_basis, old_basis)
    parent_inverse_delta = _matrix_delta(
        obj.matrix_parent_inverse,
        old_parent_inverse,
    )
    world_delta = _matrix_delta(obj.matrix_world, old_world)
    root_conversion_enabled = settings.convert_orientation is True
    expected_error = "forced transactional rewrite failure" in error
    ok = (
        raised
        and called["failed"]
        and expected_error
        and mesh_restored
        and basis_delta <= TOL
        and parent_inverse_delta <= TOL
        and world_delta <= TOL
        and root_conversion_enabled
    )
    detail = (
        "raised=%s called=%s expected_error=%s mesh=%s basis=%g "
        "parent_inverse=%g world=%g root_conversion=%s"
        % (
            raised,
            called["failed"],
            expected_error,
            mesh_restored,
            basis_delta,
            parent_inverse_delta,
            world_delta,
            root_conversion_enabled,
        )
    )
    return ok, detail


def scenario_transactional_basis_failure():
    return _scenario_transactional_failure("_assign_matrix_basis")


def scenario_transactional_world_failure():
    return _scenario_transactional_failure("_assign_matrix_world", use_delta=True)


def scenario_transactional_update_failure():
    return _scenario_transactional_failure("_update_view_layer")


SCENARIOS = {
    "instancing_preserved": scenario_instancing_preserved,
    "world_preserving": scenario_world_preserving,
    "parented_child": scenario_parented_child,
    "shape_keys": scenario_shape_keys,
    "scope_guard": scenario_scope_guard,
    "convert_orientation_disabled": scenario_convert_orientation_disabled,
    "transactional_basis_failure": scenario_transactional_basis_failure,
    "transactional_world_failure": scenario_transactional_world_failure,
    "transactional_update_failure": scenario_transactional_update_failure,
}


def main():
    results = {}
    for name, fn in SCENARIOS.items():
        try:
            ok, detail = fn()
            results[name] = {"ok": bool(ok), "detail": detail}
        except Exception as exc:  # noqa: BLE001
            results[name] = {
                "ok": False,
                "detail": "EXCEPTION: %s" % exc,
                "traceback": traceback.format_exc(),
            }
    print(OUTPUT_MARKER + json.dumps(results) + OUTPUT_MARKER)


main()
'''


def _extract_json(stdout: str) -> dict:
    start = stdout.find(OUTPUT_MARKER)
    assert start != -1, f"No result marker in Blender stdout:\n{stdout[-2000:]}"
    start += len(OUTPUT_MARKER)
    end = stdout.find(OUTPUT_MARKER, start)
    assert end != -1, f"Unterminated result marker in Blender stdout:\n{stdout[-2000:]}"
    return json.loads(stdout[start:end])


@pytest.fixture(scope="module")
def yup_results(tmp_path_factory) -> dict:
    """Run all scenarios once inside a single headless Blender process and
    return the per-scenario report. Module-scoped so Blender launches once."""
    blender = _find_blender()
    if shutil.which(blender) is None and not Path(blender).exists():
        pytest.skip("Blender not available (set BLENDERTORCP_BLENDER)")

    driver = tmp_path_factory.mktemp("yup_driver") / "driver.py"
    driver.write_text(DRIVER_SOURCE)

    cmd = [
        blender,
        "--background",
        "--factory-startup",
        "--python",
        str(driver),
        "--",
        PLUGIN_PARENT,
        OUTPUT_MARKER,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if OUTPUT_MARKER not in (proc.stdout or ""):
        pytest.fail(
            "Driver did not emit a result.\n"
            f"returncode={proc.returncode}\n"
            f"STDOUT tail:\n{(proc.stdout or '')[-3000:]}\n"
            f"STDERR tail:\n{(proc.stderr or '')[-3000:]}"
        )
    return _extract_json(proc.stdout)


def _check(yup_results: dict, name: str) -> None:
    assert name in yup_results, f"Scenario '{name}' missing from results"
    res = yup_results[name]
    if not res["ok"]:
        tb = res.get("traceback", "")
        pytest.fail(f"[{name}] {res['detail']}\n{tb}")


class TestApplyYupGeometryBake:
    def test_instancing_preserved(self, yup_results):
        _check(yup_results, "instancing_preserved")

    def test_world_preserving(self, yup_results):
        _check(yup_results, "world_preserving")

    def test_parented_child(self, yup_results):
        _check(yup_results, "parented_child")

    def test_shape_keys(self, yup_results):
        _check(yup_results, "shape_keys")

    def test_scope_guard(self, yup_results):
        _check(yup_results, "scope_guard")

    def test_convert_orientation_disabled(self, yup_results):
        _check(yup_results, "convert_orientation_disabled")

    def test_transactional_basis_failure(self, yup_results):
        _check(yup_results, "transactional_basis_failure")

    def test_transactional_world_failure(self, yup_results):
        _check(yup_results, "transactional_world_failure")

    def test_transactional_update_failure(self, yup_results):
        _check(yup_results, "transactional_update_failure")
