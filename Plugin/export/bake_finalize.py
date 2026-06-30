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
    Hierarchy-isolated objects (no in-scope parent or child) get their mesh
    baked and their transform conjugated; parented sub-hierarchies are rotated
    by left-multiplying their root only, so in-scope children inherit the
    rotation cleanly instead of being set explicitly.

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

    ## Classify scope objects by their in-scope hierarchy. We only ever set a
    ## child's world by inheritance, never explicitly: assigning a child's
    ## matrix_world right after its parent moved is unreliable in Blender (the
    ## next depsgraph update recomputes it from the basis and drifts it off).
    def has_in_scope_ancestor(obj):
        parent = obj.parent
        while parent is not None:
            if parent in scope_set:
                return True
            parent = parent.parent
        return False

    in_scope_ancestor = {obj: has_in_scope_ancestor(obj) for obj in scope}
    has_in_scope_descendant = {obj: False for obj in scope}
    for obj in scope:
        if in_scope_ancestor[obj]:
            parent = obj.parent
            while parent is not None:
                if parent in scope_set:
                    has_in_scope_descendant[parent] = True
                parent = parent.parent

    def isolated(obj):
        return not in_scope_ancestor[obj] and not has_in_scope_descendant[obj]

    ## Bake Rg into a mesh only when every object using it is (a) in scope and
    ## (b) hierarchy-isolated, so conjugating each user can't disturb a parented
    ## relative. ``mesh.transform`` mutates the datablock globally, so the user
    ## map is built from ``bpy.data.objects`` (not just this scene) to catch
    ## linked / other-scene users. Meshes that don't qualify stay un-baked and
    ## their objects rotate via the transform — instancing is preserved either
    ## way (a shared mesh is simply touched zero or one time, never split).
    mesh_users = {}
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data is not None:
            mesh_users.setdefault(obj.data, set()).add(obj)

    baked_meshes = set()
    for obj in scope:
        if obj.type == 'MESH' and obj.data is not None:
            mesh = obj.data
            if mesh in baked_meshes:
                continue
            users = mesh_users.get(mesh, set())
            if users <= scope_set and all(isolated(u) for u in users):
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

    ## Isolated objects whose mesh was baked: conjugate so the world result is
    ## exactly Rg @ world (holds for any transform, incl. non-uniform scale)
    ## while the shared mesh is touched only once. These have no in-scope
    ## children, so nothing inherits this transform.
    ## Per-object guards: a single failing assignment (e.g. a library-linked or
    ## locked object in scope) must not abort the function before it returns the
    ## restore state - otherwise the caller's finally can't undo what was already
    ## mutated, leaving the live scene partially rotated. A skipped object simply
    ## isn't rotated (mis-oriented in the export, but the scene stays restorable).
    for obj in scope:
        if obj.type == 'MESH' and obj.data in baked_meshes:
            try:
                obj.matrix_world = Rg @ old_world[obj] @ Rg_inv
            except Exception as exc:
                print("apply_yup_geometry: matrix_world (baked) failed:", exc)

    ## Everything else (lights/empties/cameras, un-baked meshes, and parented
    ## sub-hierarchies): rotate by left-multiply, but only on the roots of these
    ## sub-trees. In-scope children are skipped and inherit Rg through the
    ## parent — left-multiplication propagates cleanly to descendants, whereas
    ## conjugation does not.
    for obj in scope:
        if obj.type == 'MESH' and obj.data in baked_meshes:
            continue
        if obj.parent is not None and obj.parent in scope_set:
            continue  # in-scope child: inherits from its rotated ancestor
        try:
            obj.matrix_world = Rg @ old_world[obj]
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
