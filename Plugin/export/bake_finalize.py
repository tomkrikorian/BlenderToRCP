"""Shared post-bake export prep.

Used by both the interactive background runner (``bake_export_runner.py``) and
the CLI/API ``bake_export`` command so the two paths behave identically:
choosing Unlit vs Lit-PBR, and the optional Y-up geometry bake.
"""

from __future__ import annotations

import math

import bpy


def resolve_force_unlit(settings) -> bool:
    """Whether baked materials should be authored as RealityKit Unlit.

    "Material Color Only - Lit PBR" (LIT_ALBEDO) authors Lit PBR so
    RealityKit lights the baked color. Every other mode stays Unlit:
    "Material Color Only - Unlit" (UNLIT_ALBEDO) by design, and "Lighting &
    Shadows" (LIT_IBL) because it bakes lighting into the albedo.
    """
    return str(getattr(settings, "bake_mode", "LIT_IBL")) != "LIT_ALBEDO"


def apply_force_unlit(settings) -> None:
    settings.force_unlit_materials = resolve_force_unlit(settings)


def should_apply_yup(settings) -> bool:
    """Y-up geometry bake only applies when orientation conversion is enabled.

    The UI only exposes the ``apply_yup_geometry`` checkbox under
    ``convert_orientation``; this keeps the runtime behavior consistent with
    that, so a stale ``apply_yup_geometry=True`` does nothing while orientation
    conversion is off.
    """
    return bool(getattr(settings, "convert_orientation", False)) and bool(
        getattr(settings, "apply_yup_geometry", False)
    )


def apply_yup_geometry_bake(context, settings, objects=None) -> dict:
    """Bake a -90deg X rotation into geometry so the export is natively Y-up.

    Every exported object's world geometry ends up rotated -90deg about X (Z-up
    -> Y-up). The rotation is baked into each unique *mesh datablock* exactly
    once (``mesh.transform``), and each object's transform is adjusted to hold
    its world placement, so linked / instanced duplicates keep sharing a single
    mesh. (The old approach rotated each object then called
    ``bpy.ops.object.transform_apply``, which refuses multi-user data and, on its
    ``make_single_user`` fallback, split shared meshes into per-object copies —
    silently destroying instancing.)

    Scope: a full-scene export rotates every object in the scene; a
    selected-objects-only export (``objects`` given) rotates exactly that set.
    Each unique mesh datablock whose users are all in scope is baked once
    (instancing preserved); then every object's world is set explicitly in
    top-down (parent-first) order, so the result holds without relying on
    inheritance. A baked mesh's object is conjugated (``Rg @ world @ Rg_inv``)
    so the baked verts land at ``Rg @ world``; lights / cameras / un-baked
    meshes are left-multiplied (``Rg @ world``) to carry the rotation on their
    transform. Empties are left untouched - a grouping empty never receives a
    -90 root rotation; the orientation lives in its baked child geometry
    instead. (The previous approach rotated parented sub-tree roots, which left
    a -90 on grouping empties; and ``transform_apply`` split shared meshes,
    destroying instancing.)

    Disables ``convert_orientation`` afterwards so the exporter doesn't author
    its own root -90deg on top.

    Returns a restore-state dict (baked meshes, per-object local-transform
    snapshot, the inverse rotation, and the original ``convert_orientation``)
    that ``restore_yup_geometry_bake`` consumes to undo this for an in-process
    export. The background bake runner ignores it (its scene is throwaway).
    """
    from mathutils import Matrix

    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    orig_convert_orientation = bool(getattr(settings, "convert_orientation", False))
    scope = list(objects) if objects is not None else list(context.scene.objects)
    if not scope:
        settings.convert_orientation = False
        return {
            "baked_meshes": set(),
            "orig_basis": {},
            "rg_inv": None,
            "orig_convert_orientation": orig_convert_orientation,
        }
    scope_set = set(scope)

    Rg = Matrix.Rotation(math.radians(-90), 4, 'X')
    Rg_inv = Rg.inverted()

    ## Snapshot each scope object's local transform (order-independent, unlike
    ## matrix_world) so an in-process export can restore the scene exactly.
    orig_basis = {obj: obj.matrix_basis.copy() for obj in scope}

    ## Bake Rg into a mesh datablock only when every object using it is in scope,
    ## so the shared datablock bake is valid for all users and instancing is
    ## preserved (the datablock is touched at most once, never split). The user
    ## map is built from ``bpy.data.objects`` - not just this scene - to catch
    ## linked / other-scene users that the bake would otherwise corrupt.
    mesh_users = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data is not None:
            mesh_users.setdefault(obj.data, set()).add(obj)

    baked_meshes = set()
    for obj in scope:
        if obj.type == 'MESH' and obj.data is not None and obj.data not in baked_meshes:
            mesh = obj.data
            if mesh_users.get(mesh, set()) <= scope_set:
                try:
                    ## shape_keys=True so shape-key coordinates rotate with the
                    ## base mesh; otherwise keyed meshes would deform wrongly.
                    mesh.transform(Rg, shape_keys=True)
                    mesh.update()
                    baked_meshes.add(mesh)
                except Exception as exc:
                    print("apply_yup_geometry: mesh.transform failed:", exc)

    ## Snapshot world matrices before moving anything.
    old_world = {obj: obj.matrix_world.copy() for obj in scope}

    def _target_world(obj):
        ## Baked mesh: conjugate so the baked verts (Rg @ v) land at Rg @ world.
        if obj.type == 'MESH' and obj.data in baked_meshes:
            return Rg @ old_world[obj] @ Rg_inv
        ## Empties carry no geometry and every child's world is set explicitly
        ## below, so a grouping empty never needs (and must not get) a -90: leave
        ## it as-is. The orientation lives in its baked child geometry.
        if obj.type == 'EMPTY':
            return old_world[obj]
        ## Lights / cameras / un-baked meshes: rotate via the transform.
        return Rg @ old_world[obj]

    ## Assign every object's world explicitly, parents before children (by
    ## in-scope depth). Setting a child against its already-final parent + a
    ## single trailing update is stable in Blender, so this handles arbitrary
    ## hierarchies - including meshes parented under a grouping empty - without
    ## relying on inheritance. Per-object guards keep one failing assignment
    ## (e.g. a library-linked / locked object) from aborting before the restore
    ## state is returned: a skipped object is just un-rotated in the export,
    ## never an un-restorable scene.
    def _in_scope_depth(obj):
        depth = 0
        parent = obj.parent
        while parent is not None:
            if parent in scope_set:
                depth += 1
            parent = parent.parent
        return depth

    for obj in sorted(scope, key=_in_scope_depth):
        try:
            obj.matrix_world = _target_world(obj)
        except Exception as exc:
            print("apply_yup_geometry: matrix_world failed:", exc)

    try:
        context.view_layer.update()
    except Exception as exc:
        print("apply_yup_geometry: view_layer.update failed:", exc)

    ## Geometry is now natively Y-up; don't let the exporter add its own root -90deg.
    settings.convert_orientation = False

    return {
        "baked_meshes": baked_meshes,
        "orig_basis": orig_basis,
        "rg_inv": Rg_inv,
        "orig_convert_orientation": orig_convert_orientation,
    }


def restore_yup_geometry_bake(context, settings, state) -> None:
    """Undo ``apply_yup_geometry_bake`` so an in-process export leaves the live
    scene exactly as it was.

    Reverses the mesh rotation (``Rg_inv`` on each baked datablock, once),
    restores every scope object's local transform from the snapshot, and puts
    ``convert_orientation`` back. Run from a ``finally`` so a failed export can't
    leave the user's scene rotated.
    """
    if not state:
        return

    rg_inv = state.get("rg_inv")
    if rg_inv is not None:
        for mesh in state.get("baked_meshes", set()):
            try:
                mesh.transform(rg_inv, shape_keys=True)
                mesh.update()
            except Exception as exc:
                print("restore_yup_geometry_bake: mesh.transform failed:", exc)

    for obj, basis in state.get("orig_basis", {}).items():
        try:
            obj.matrix_basis = basis
        except Exception:
            pass

    if settings is not None and "orig_convert_orientation" in state:
        try:
            settings.convert_orientation = state["orig_convert_orientation"]
        except Exception:
            pass

    try:
        context.view_layer.update()
    except Exception:
        pass


def set_stage_up_axis_y(usd_path, diagnostics=None) -> None:
    """Force the exported stage's upAxis to Y (geometry was baked Y-up).

    With ``convert_orientation=False`` the exporter won't author an up-axis, so
    set it explicitly to match the baked geometry. This is the linchpin of the
    Y-up feature, so a failure is surfaced through diagnostics (not just stdout)
    — otherwise the USD would silently ship mis-oriented.
    """
    try:
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(usd_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        stage.GetRootLayer().Save()
    except Exception as exc:
        message = f"apply_yup_geometry: failed to set upAxis: {exc}"
        print(message)
        if diagnostics is not None:
            try:
                diagnostics.add_warning(message)
            except Exception:
                pass
